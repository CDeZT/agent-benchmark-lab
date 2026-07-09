// Book Library Frontend
const API = '/api';

async function apiCall(method, path, body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);
    const response = await fetch(`${API}${path}`, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
}

async function loadStats() {
    try {
        const stats = await apiCall('GET', '/stats');
        document.getElementById('stat-total').textContent = stats.total_books;
        document.getElementById('stat-reading-list').textContent = stats.total_in_reading_list;
        document.getElementById('stat-avg-rating').textContent =
            stats.average_rating ? stats.average_rating.toFixed(1) : 'N/A';
    } catch (e) { console.error('Failed to load stats:', e); }
}

async function loadBooks() {
    try {
        const books = await apiCall('GET', '/books');
        const tbody = document.getElementById('book-list');
        tbody.innerHTML = books.map(b => `<tr>
            <td>${escapeHtml(b.title)}</td><td>${escapeHtml(b.author)}</td>
            <td>${escapeHtml(b.genre||'fiction')}</td><td>${b.rating?b.rating.toFixed(1):'-'}</td>
            <td>${b.pages||'-'}</td>
            <td><button onclick="addToReadingList(${b.id})">Add to List</button>
            <button class="danger" onclick="deleteBook(${b.id})">Delete</button></td>
        </tr>`).join('');
    } catch (e) { console.error('Failed to load books:', e); }
}

async function addBook() {
    const title = document.getElementById('book-title').value.trim();
    const author = document.getElementById('book-author').value.trim();
    if (!title || !author) { showMsg('add-message','Title and author required','error'); return; }
    const body = { title, author, genre: document.getElementById('book-genre').value };
    const isbn = document.getElementById('book-isbn').value.trim();
    const rating = parseFloat(document.getElementById('book-rating').value);
    const pages = parseInt(document.getElementById('book-pages').value);
    if (isbn) body.isbn = isbn;
    if (!isNaN(rating)) body.rating = rating;
    if (!isNaN(pages)) body.pages = pages;
    try {
        await apiCall('POST', '/books', body);
        showMsg('add-message','Book added!','success');
        ['book-title','book-author','book-isbn','book-rating','book-pages'].forEach(id=>document.getElementById(id).value='');
        loadBooks(); loadStats();
    } catch (e) { showMsg('add-message',e.message,'error'); }
}

async function deleteBook(id) {
    if (!confirm('Delete this book?')) return;
    try { await apiCall('DELETE',`/books/${id}`); loadBooks(); loadReadingList(); loadStats(); }
    catch (e) { alert('Failed: '+e.message); }
}

async function searchBooks() {
    const q = document.getElementById('search-query').value.trim();
    if (!q) return;
    try {
        const results = await apiCall('GET',`/books/search?q=${encodeURIComponent(q)}`);
        const c = document.getElementById('search-results');
        if (!results.length) { c.innerHTML='<p>No results.</p>'; return; }
        c.innerHTML = `<table><thead><tr><th>Title</th><th>Author</th><th>ISBN</th><th>Action</th></tr></thead><tbody>${
            results.map(b=>`<tr><td>${escapeHtml(b.title)}</td><td>${escapeHtml(b.author)}</td><td>${escapeHtml(b.isbn||'-')}</td><td><button onclick="addToReadingList(${b.id})">Add to List</button></td></tr>`).join('')
        }</tbody></table>`;
    } catch (e) { document.getElementById('search-results').innerHTML=`<p class="message error">Search failed: ${e.message}</p>`; }
}

async function loadReadingList() {
    try {
        const items = await apiCall('GET','/reading-list');
        document.getElementById('reading-list').innerHTML = items.map(i=>`<tr>
            <td>${escapeHtml(i.title)}</td><td>${escapeHtml(i.author)}</td>
            <td><span class="status-badge status-${i.status}">${fmtStatus(i.status)}</span></td>
            <td>${escapeHtml(i.notes||'-')}</td>
            <td><select onchange="updateReadingStatus(${i.id},this.value)">
                <option value="want_to_read" ${i.status==='want_to_read'?'selected':''}>Want to Read</option>
                <option value="reading" ${i.status==='reading'?'selected':''}>Reading</option>
                <option value="finished" ${i.status==='finished'?'selected':''}>Finished</option>
            </select>
            <button class="danger" onclick="removeFromReadingList(${i.id})">Remove</button></td>
        </tr>`).join('');
    } catch (e) { console.error('Failed:', e); }
}

async function addToReadingList(bookId) {
    try { await apiCall('POST','/reading-list',{book_id:bookId,status:'want_to_read'}); loadReadingList(); loadStats(); }
    catch (e) { alert('Failed: '+e.message); }
}

async function updateReadingStatus(id, status) {
    try { await apiCall('PUT',`/reading-list/${id}`,{status}); loadReadingList(); }
    catch (e) { alert('Failed: '+e.message); }
}

async function removeFromReadingList(id) {
    try { await apiCall('DELETE',`/reading-list/${id}`); loadReadingList(); loadStats(); }
    catch (e) { alert('Failed: '+e.message); }
}

function escapeHtml(t) { if(!t)return''; const d=document.createElement('div'); d.textContent=t; return d.innerHTML; }
function fmtStatus(s) { return {want_to_read:'Want to Read',reading:'Reading',finished:'Finished'}[s]||s; }
function showMsg(id,txt,type) { const e=document.getElementById(id); e.textContent=txt; e.className=`message ${type}`; setTimeout(()=>{e.className='message';},3000); }

document.addEventListener('DOMContentLoaded',()=>{ loadStats(); loadBooks(); loadReadingList(); });
