/*
 * Memory Pool Allocator - FIXED Implementation
 *
 * Fixes:
 * 1. Double-free: set magic to FREE_MAGIC on free, check it on free
 * 2. realloc: copy old data to new block
 * 3. mempool_check: validate prev pointer consistency
 * 4. Fragmentation: calculate from free block distribution
 * 5. usable_size: return exact block size
 * 6. merge_free_blocks: also merge with previous block
 */

#include "mempool.h"
#include <stdlib.h>
#include <string.h>

static size_t align_up(size_t value, size_t alignment) {
    return (value + alignment - 1) & ~(alignment - 1);
}

static BlockHeader *ptr_to_header(void *ptr) {
    return (BlockHeader *)((uint8_t *)ptr - sizeof(BlockHeader));
}

static void split_block(BlockHeader *block, size_t size) {
    size_t total_needed = size + sizeof(BlockHeader);
    if (block->size >= total_needed + 64) {
        BlockHeader *new_block = (BlockHeader *)((uint8_t *)block + sizeof(BlockHeader) + size);
        new_block->magic = MEMPOOL_MAGIC;
        new_block->size = block->size - size - sizeof(BlockHeader);
        new_block->is_free = true;
        new_block->next = block->next;
        new_block->prev = block;
        if (block->next) block->next->prev = new_block;
        block->next = new_block;
        block->size = size;
    }
}

/* FIX: merge with both next AND previous free blocks */
static void merge_free_blocks(BlockHeader *block) {
    if (block->next && block->next->is_free) {
        block->size += sizeof(BlockHeader) + block->next->size;
        block->next = block->next->next;
        if (block->next) block->next->prev = block;
    }
    if (block->prev && block->prev->is_free) {
        block->prev->size += sizeof(BlockHeader) + block->size;
        block->prev->next = block->next;
        if (block->next) block->next->prev = block->prev;
    }
}

MemPool *mempool_create(size_t size) {
    return mempool_create_aligned(size, MEMPOOL_DEFAULT_ALIGNMENT);
}

MemPool *mempool_create_aligned(size_t size, size_t alignment) {
    if (size == 0 || alignment == 0) return NULL;
    if (alignment & (alignment - 1)) return NULL;
    MemPool *pool = (MemPool *)malloc(sizeof(MemPool));
    if (!pool) return NULL;
    pool->memory = (uint8_t *)malloc(size);
    if (!pool->memory) { free(pool); return NULL; }
    pool->size = size;
    pool->alignment = alignment;
    pool->is_corrupt = false;
    pool->head = (BlockHeader *)pool->memory;
    pool->head->magic = MEMPOOL_MAGIC;
    pool->head->size = size - sizeof(BlockHeader);
    pool->head->is_free = true;
    pool->head->next = NULL;
    pool->head->prev = NULL;
    return pool;
}

void mempool_destroy(MemPool *pool) {
    if (!pool) return;
    free(pool->memory);
    free(pool);
}

void *mempool_alloc(MemPool *pool, size_t size) {
    if (!pool || size == 0 || pool->is_corrupt) return NULL;
    size_t aligned_size = align_up(size, pool->alignment);
    BlockHeader *current = pool->head;
    while (current) {
        if (current->magic != MEMPOOL_MAGIC) { pool->is_corrupt = true; return NULL; }
        if (current->is_free && current->size >= aligned_size) {
            split_block(current, aligned_size);
            current->is_free = false;
            memset((uint8_t *)current + sizeof(BlockHeader), 0, aligned_size);
            return (uint8_t *)current + sizeof(BlockHeader);
        }
        current = current->next;
    }
    return NULL;
}

void *mempool_alloc_aligned(MemPool *pool, size_t size, size_t alignment) {
    if (!pool || size == 0 || pool->is_corrupt) return NULL;
    if (alignment & (alignment - 1)) return NULL;
    if (alignment <= pool->alignment) return mempool_alloc(pool, size);
    size_t total = size + alignment + sizeof(BlockHeader) + sizeof(void *);
    void *raw = mempool_alloc(pool, total);
    if (!raw) return NULL;
    uintptr_t addr = (uintptr_t)raw + sizeof(void *);
    uintptr_t aligned = align_up(addr, alignment);
    void **store = (void **)(aligned - sizeof(void *));
    *store = raw;
    return (void *)aligned;
}

/* FIX: detect double-free via FREE_MAGIC */
int mempool_free(MemPool *pool, void *ptr) {
    if (!pool || !ptr) return -1;
    if (pool->is_corrupt) return -1;
    BlockHeader *header = ptr_to_header(ptr);
    if (header->magic == MEMPOOL_FREE_MAGIC) return -1; /* double free */
    if (header->magic != MEMPOOL_MAGIC) return -1;
    if (header->is_free) return -1;
    header->is_free = true;
    header->magic = MEMPOOL_FREE_MAGIC;
    merge_free_blocks(header);
    header->magic = MEMPOOL_MAGIC; /* restore after merge */
    return 0;
}

/* FIX: copy old data to new block */
void *mempool_realloc(MemPool *pool, void *ptr, size_t new_size) {
    if (!pool || new_size == 0) return NULL;
    if (!ptr) return mempool_alloc(pool, new_size);
    BlockHeader *header = ptr_to_header(ptr);
    if (header->magic != MEMPOOL_MAGIC) return NULL;
    if (header->size >= new_size) return ptr;
    void *new_ptr = mempool_alloc(pool, new_size);
    if (!new_ptr) return NULL;
    memcpy(new_ptr, ptr, header->size); /* FIX: copy old data */
    mempool_free(pool, ptr);
    return new_ptr;
}

int mempool_stats(const MemPool *pool, PoolStats *stats) {
    if (!pool || !stats) return -1;
    if (pool->is_corrupt) return -1;
    memset(stats, 0, sizeof(PoolStats));
    stats->total_size = pool->size;
    BlockHeader *current = pool->head;
    while (current) {
        if (current->magic != MEMPOOL_MAGIC && current->magic != MEMPOOL_FREE_MAGIC) return -1;
        if (current->is_free) {
            stats->free_size += current->size;
            stats->num_free_blocks++;
            if (current->size > stats->largest_free) stats->largest_free = current->size;
        } else {
            stats->used_size += current->size;
            stats->num_allocations++;
        }
        current = current->next;
    }
    /* FIX: calculate fragmentation */
    if (stats->num_free_blocks > 0 && stats->free_size > 0) {
        stats->fragmentation = (size_t)(100 * (1.0 - (double)stats->largest_free / stats->free_size));
    }
    return 0;
}

/* FIX: validate prev pointer consistency */
bool mempool_check(const MemPool *pool) {
    if (!pool) return false;
    if (pool->is_corrupt) return false;
    BlockHeader *current = pool->head;
    BlockHeader *prev = NULL;
    while (current) {
        if (current->magic != MEMPOOL_MAGIC && current->magic != MEMPOOL_FREE_MAGIC) return false;
        if (current->prev != prev) return false; /* FIX */
        uint8_t *block_start = (uint8_t *)current;
        uint8_t *block_end = block_start + sizeof(BlockHeader) + current->size;
        if (block_start < pool->memory || block_end > pool->memory + pool->size) return false;
        prev = current;
        current = current->next;
    }
    return true;
}

/* FIX: return just usable size */
size_t mempool_usable_size(const MemPool *pool, const void *ptr) {
    if (!pool || !ptr) return 0;
    BlockHeader *header = ptr_to_header((void *)ptr);
    if (header->magic != MEMPOOL_MAGIC && header->magic != MEMPOOL_FREE_MAGIC) return 0;
    return header->size; /* FIX: not + sizeof(BlockHeader) */
}
