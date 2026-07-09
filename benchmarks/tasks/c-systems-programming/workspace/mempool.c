/*
 * Memory Pool Allocator Implementation
 *
 * BUGS TO FIX:
 * 1. Double-free detection doesn't work - magic not set to FREE_MAGIC on free
 * 2. mempool_realloc doesn't copy old data when allocating a new block
 * 3. mempool_check doesn't validate the linked list prev pointers
 * 4. Fragmentation metric is always 0 (not implemented)
 * 5. mempool_usable_size returns wrong value (includes header)
 * 6. merge_free_blocks doesn't merge with previous block
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

static void merge_free_blocks(BlockHeader *block) {
    if (block->next && block->next->is_free) {
        block->size += sizeof(BlockHeader) + block->next->size;
        block->next = block->next->next;
        if (block->next) block->next->prev = block;
    }
    /* BUG: missing merge with previous block */
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
    size_t total = size + alignment + sizeof(BlockHeader);
    void *raw = mempool_alloc(pool, total);
    if (!raw) return NULL;
    uintptr_t addr = (uintptr_t)raw;
    uintptr_t aligned = (addr + alignment - 1) & ~(alignment - 1);
    return (void *)aligned;
}

int mempool_free(MemPool *pool, void *ptr) {
    if (!pool || !ptr) return -1;
    if (pool->is_corrupt) return -1;
    BlockHeader *header = ptr_to_header(ptr);
    if (header->magic != MEMPOOL_MAGIC) return -1;
    if (header->is_free) return -1;
    /* BUG: should set magic to MEMPOOL_FREE_MAGIC */
    header->is_free = true;
    merge_free_blocks(header);
    return 0;
}

void *mempool_realloc(MemPool *pool, void *ptr, size_t new_size) {
    if (!pool || new_size == 0) return NULL;
    if (!ptr) return mempool_alloc(pool, new_size);
    BlockHeader *header = ptr_to_header(ptr);
    if (header->magic != MEMPOOL_MAGIC) return NULL;
    if (header->size >= new_size) return ptr;
    void *new_ptr = mempool_alloc(pool, new_size);
    if (!new_ptr) return NULL;
    /* BUG: missing memcpy(new_ptr, ptr, header->size) */
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
        if (current->magic != MEMPOOL_MAGIC) return -1;
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
    /* BUG: fragmentation always 0 */
    stats->fragmentation = 0;
    return 0;
}

bool mempool_check(const MemPool *pool) {
    if (!pool) return false;
    if (pool->is_corrupt) return false;
    BlockHeader *current = pool->head;
    BlockHeader *prev = NULL;
    while (current) {
        if (current->magic != MEMPOOL_MAGIC) return false;
        /* BUG: should validate current->prev == prev */
        uint8_t *block_start = (uint8_t *)current;
        uint8_t *block_end = block_start + sizeof(BlockHeader) + current->size;
        if (block_start < pool->memory || block_end > pool->memory + pool->size) return false;
        prev = current;
        current = current->next;
    }
    return true;
}

size_t mempool_usable_size(const MemPool *pool, const void *ptr) {
    if (!pool || !ptr) return 0;
    BlockHeader *header = ptr_to_header((void *)ptr);
    if (header->magic != MEMPOOL_MAGIC) return 0;
    /* BUG: returns size + header, should return just size */
    return header->size + sizeof(BlockHeader);
}
