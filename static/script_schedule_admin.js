document.addEventListener('DOMContentLoaded', () => {
  loadSchedules();
});

async function loadSchedules() {
  try {
    const [pendingRes, confirmedRes] = await Promise.all([
      fetch('/schedule/api/pending'),
      fetch('/schedule/api/events')
    ]);
    const pending = await pendingRes.json();
    const confirmed = await confirmedRes.json();
    
    renderPending(pending);
    renderConfirmed(confirmed);
  } catch(err) {
    console.error("Failed to load schedules", err);
  }
}

function renderPending(pending) {
  const tbody = document.getElementById('pending-tbody');
  if(pending.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">대기 중인 일정이 없습니다.</td></tr>';
    return;
  }
  
  tbody.innerHTML = pending.map(s => `
    <tr>
      <td>${escapeHTML(s.requester_name)}</td>
      <td><strong>${escapeHTML(s.title)}</strong></td>
      <td>${s.date}</td>
      <td>${s.time_start || '종일'} ~ ${s.time_end || ''}</td>
      <td>${escapeHTML(s.location || '-')}</td>
      <td>${escapeHTML(s.description || '')}</td>
      <td class="actions">
        <button type="button" class="btn-approve" onclick="confirmSchedule(${s.id})">승인</button>
        <button type="button" class="btn-delete" onclick="deleteSchedule(${s.id}, this)">거절</button>
      </td>
    </tr>
  `).join('');
}

function renderConfirmed(confirmed) {
  const tbody = document.getElementById('confirmed-tbody');
  if(confirmed.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">확정된 일정이 없습니다.</td></tr>';
    return;
  }
  
  tbody.innerHTML = confirmed.map(s => `
    <tr>
      <td>${escapeHTML(s.requester_name)}</td>
      <td><strong>${escapeHTML(s.title)}</strong></td>
      <td>${s.date}</td>
      <td>${s.time_start || '종일'} ~ ${s.time_end || ''}</td>
      <td>${escapeHTML(s.location || '-')}</td>
      <td>${escapeHTML(s.description || '')}</td>
      <td class="actions">
        <button type="button" class="btn-delete" onclick="deleteSchedule(${s.id}, this)">삭제</button>
      </td>
    </tr>
  `).join('');
}

async function confirmSchedule(id) {
  try {
    const res = await fetch(`/schedule/api/confirm/${id}`, { method: 'PUT' });
    if(res.ok) {
      loadSchedules();
    } else {
      const data = await res.json();
      console.error("오류가 발생했습니다: " + (data.error || res.statusText));
      alert("오류가 발생했습니다: " + (data.error || res.statusText));
    }
  } catch(err) {
    console.error(err);
    alert("네트워크 통신 중 오류가 발생했습니다.");
  }
}

// Store pending deletions to act as a double-click confirm without native popups
const pendingDeletes = new Set();

async function deleteSchedule(id, btnElement) {
  try {
    if (!pendingDeletes.has(id)) {
      // First click
      pendingDeletes.add(id);
      const originalText = btnElement.innerText;
      btnElement.innerText = "정말 삭제?";
      
      // Reset after 3 seconds
      setTimeout(() => {
        if (pendingDeletes.has(id)) {
          pendingDeletes.delete(id);
          btnElement.innerText = originalText;
        }
      }, 3000);
      return;
    }

    // Second click (Confirmed)
    pendingDeletes.delete(id);
    const res = await fetch(`/schedule/api/${id}`, { method: 'DELETE' });
    if(res.ok) {
      loadSchedules();
    } else {
      const data = await res.json();
      console.error("오류가 발생했습니다: " + (data.error || res.statusText));
      alert("오류가 발생했습니다: " + (data.error || res.statusText));
    }
  } catch(err) { 
    console.error(err);
    alert("네트워크 통신 중 오류가 발생했습니다.");
  }
}

function escapeHTML(str) {
  return String(str).replace(/[&<>'"]/g, 
    tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag)
  );
}
