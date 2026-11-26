'use strict';
(() => {
  const sidebar = document.getElementById('sidebar');
  const shade = document.getElementById('drawer-shade');
  const open = document.getElementById('menu-open');
  const toggle = (show) => {
    if (!sidebar || !shade || !open) return;
    sidebar.classList.toggle('open', show);
    shade.hidden = !show;
    open.setAttribute('aria-expanded', show ? 'true' : 'false');
  };
  open?.addEventListener('click', () => toggle(!sidebar.classList.contains('open')));
  shade?.addEventListener('click', () => toggle(false));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') toggle(false); });
  document.querySelectorAll('[data-show-password]').forEach(button => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.showPassword);
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
      button.textContent = input.type === 'password' ? 'Hiện' : 'Ẩn';
    });
  });
  // Read-only, authenticated previews. Changes to selectors NEVER submit a POST.
  document.querySelectorAll('[data-preview-kind]').forEach(panel => {
    const form = document.querySelector('.form-layout form');
    if (!form) return;
    const kind = panel.dataset.previewKind;
    const asset = form.querySelector('[name="asset_id"]');
    const person = form.querySelector('[name="personnel_id"]');
    const message = panel.querySelector('[data-preview-message]');
    const list = panel.querySelector('[data-preview-list]');
    const details = panel.querySelector('[data-preview-details]');
    let controller = null;
    const describe = text => { if (message) message.textContent = text; };
    const clearContent = () => {
      if (list) list.replaceChildren();
      if (details) details.replaceChildren();
    };
    const addLine = text => {
      const p = document.createElement('p');
      p.className = 'preview-detail';
      p.textContent = text;
      details?.appendChild(p);
    };
    async function refresh() {
      controller?.abort();
      clearContent();
      if (!asset?.value) {
        describe(kind === 'booking' ? 'Chọn thiết bị để xem lịch đã đặt.' : 'Chọn hóa chất để xem tồn kho và điều kiện cấp phát.');
        return;
      }
      controller = new AbortController();
      const params = new URLSearchParams({asset_id: asset.value});
      if (kind === 'dispense' && person?.value) params.set('personnel_id', person.value);
      describe('Đang kiểm tra dữ liệu mới nhất…');
      try {
        const response = await fetch(panel.dataset.previewUrl + '?' + params.toString(), {
          credentials: 'same-origin', headers: {'Accept': 'application/json'},
          signal: controller.signal, cache: 'no-store'
        });
        if (!response.ok) throw new Error('unavailable');
        const data = await response.json();
        if (kind === 'booking') {
          describe(data.message || 'Không tìm thấy thông tin lịch.');
          (data.reservations || []).forEach(booking => {
            const li = document.createElement('li');
            li.textContent = booking.start + ' đến ' + booking.end + (booking.status ? ' · ' + booking.status : '');
            list?.appendChild(li);
          });
          if (data.selected && data.asset_status !== 'Sẵn sàng') {
            const li = document.createElement('li');
            li.textContent = 'Trạng thái tài sản: ' + data.asset_status + '. Hãy xác nhận điều kiện sử dụng.';
            list?.prepend(li);
          }
        } else {
          describe(data.message || 'Chọn người nhận để kiểm tra chứng chỉ.');
          if (data.selected) {
            addLine('Tồn kho: ' + data.stock + ' ' + data.unit + ' · Cấp nguy hiểm: ' + data.hazard_level);
            addLine('Tình trạng tài sản: ' + data.status + ' · Hạn dùng: ' + data.expiry_date);
            const submit = form.querySelector('button[type=submit]');
            if (submit) submit.disabled = Boolean(data.expired);
            addLine('Có thể cấp phát: ' + (data.dispensable_stock || (data.expired ? '0' : data.stock)) + ' ' + data.unit);
            if (data.expired) addLine('Hóa chất đã hết hạn. Không thể cấp phát; hãy nhập lô mới.');
            if (data.has_recipient) addLine('Chứng chỉ người nhận: ' + data.max_valid_level +
              (data.certificate_eligible ? ' · Đạt yêu cầu cấp.' : ' · Chưa đủ cấp yêu cầu.'));
          }
        }
      } catch (error) {
        if (error.name !== 'AbortError') describe('Không thể tải thông tin xem trước. CSDL vẫn kiểm tra khi gửi.');
      }
    }
    asset?.addEventListener('change', refresh);
    if (kind === 'dispense') person?.addEventListener('change', refresh);
    refresh();
  });
  document.querySelectorAll('form[data-allocation-form]').forEach(form => {
    const asset = form.querySelector('[name="asset_id"]');
    const unit = form.querySelector('[data-allocation-unit]');
    const qty = form.querySelector('[name=allocated_qty]');
    const refresh = () => {
      if (!unit) return;
      const selected = asset?.selectedOptions?.[0];
      const measure = selected?.dataset.unit;
      const equipment=selected?.dataset.type==='equipment' || (Boolean(asset?.value) && !measure);
      const label=form.querySelector('[data-allocation-unit-label]');
      if(label) label.textContent=!asset?.value?'—':equipment?'máy':(measure?.toLowerCase()==='ml'?'mL':measure || '—');
      if (qty) {
        qty.readOnly=equipment; qty.min=equipment?'1':'0.001'; qty.step=equipment?'1':'0.001';
        if(equipment){qty.value='1';qty.max='1';}
        else {qty.removeAttribute('max');}
      }
      unit.textContent = !asset?.value ? 'Chọn tài sản để xem đơn vị phân bổ.' : measure ?
        'Đơn vị phân bổ theo tài sản đã chọn: ' + measure + '. Thao tác này không trừ tồn kho.' :
        'Mỗi mã thiết bị tương ứng 1 máy. Số lượng phân bổ cố định bằng 1.';
    };
    asset?.addEventListener('change', refresh);
    refresh();
  });
  document.querySelectorAll('form[data-busy-form]').forEach(form => {
    let pending = false;
    form.addEventListener('submit', event => {
      if (pending) { event.preventDefault(); return; }
      if (form.hasAttribute('data-confirm-dispense')) {
        const asset = form.querySelector('[name=asset_id]');
        const recipient = form.querySelector('[name=personnel_id]');
        const project = form.querySelector('[name=project_id]');
        const quantity = form.querySelector('[name=quantity]');
        const purpose = form.querySelector('[name=purpose]');
        const label = node => node?.selectedOptions?.[0]?.textContent?.trim() || 'Chưa chọn';
        const summary = 'Xác nhận cấp phát hóa chất?\n\n'
          + 'Hóa chất: ' + label(asset) + '\n'
          + 'Người nhận: ' + label(recipient) + '\n'
          + 'Số lượng: ' + (quantity?.value || '—') + '\n'
          + 'Đề tài: ' + label(project) + '\n'
          + 'Mục đích: ' + (purpose?.value || 'Không ghi') + '\n\n'
          + 'Hệ thống sẽ ghi nhật ký và trừ tồn kho nếu điều kiện hợp lệ.';
        if (!window.confirm(summary)) { event.preventDefault(); return; }
      }
      pending = true;
      const button = event.submitter || form.querySelector('button[type=submit]');
      if (button) window.requestAnimationFrame(() => {
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.textContent = 'Đang xử lý…';
      });
    });
    window.addEventListener('pageshow', () => {
      pending = false;
      form.querySelectorAll('button:disabled[data-original-text]').forEach(btn => {
        btn.disabled = false;
        btn.textContent = btn.dataset.originalText;
      });
    });
  });
})();

// Separate controls avoid rewriting a native datetime editor while typing.
(() => {
  const vnStamp = ms => new Date(ms + 7*3600000).toISOString().slice(0,16);
  document.querySelectorAll('form[data-booking-time-grid]').forEach(form => {
    const groups=[...form.querySelectorAll('[data-booking-time]')];
    const sync = validate => {
      groups.forEach(group => {
        const name=group.dataset.bookingTime;
        const day=group.querySelector('[type=date]');
        const hour=group.querySelector('[name$="_hour"]');
        const minute=group.querySelector('[name$="_minute"]');
        const hidden=group.querySelector('[type=hidden]');
        day.setCustomValidity('');
        hidden.value=day.value && hour.value && minute.value ? day.value+'T'+hour.value+':'+minute.value : '';
      });
      if (!validate) return;
      const start=form.querySelector('[name=start_time]');
      const end=form.querySelector('[name=end_time]');
      const startDay=form.querySelector('[name=start_time_date]');
      const endDay=form.querySelector('[name=end_time_date]');
      if (start?.value && start.value <= vnStamp(Date.now()))
        startDay.setCustomValidity('Bắt đầu phải ở tương lai, theo giờ Việt Nam.');
      if (start?.value && end?.value && end.value <= start.value)
        endDay.setCustomValidity('Kết thúc phải sau bắt đầu ít nhất 15 phút.');
    };
    groups.forEach(group => {
      group.addEventListener('input',() => sync(false));
      group.addEventListener('change',() => sync(true));
    });
    form.addEventListener('submit',event => {
      sync(true);
      if (!form.checkValidity()) {
        event.preventDefault();event.stopImmediatePropagation();form.reportValidity();
      }
    },true);
    sync(false);
  });
})();

(() => {
 document.querySelectorAll('[data-schedule-book]').forEach(track => {
  track.addEventListener('click',event => {
   if (event.target.closest('.schedule-slot')) return;
   const rect=track.getBoundingClientRect();
   const first=Number(track.dataset.first)*60, last=Number(track.dataset.last)*60;
   const minute=Math.min(last-15,first+Math.floor((event.clientX-rect.left)/rect.width*(last-first)/15)*15);
   const wall=track.dataset.day+'T'+String(Math.floor(minute/60)).padStart(2,'0')+':'+String(minute%60).padStart(2,'0');
   const ms=Date.parse(wall+':00+07:00');
   if (!Number.isFinite(ms) || ms<=Date.now()) return;
   const end=new Date(ms+3600000+7*3600000).toISOString().slice(0,16);
   const url=new URL(track.dataset.bookUrl,window.location.origin);
   url.searchParams.set('start_time',wall);url.searchParams.set('end_time',end);
   window.location.assign(url);
  });
 });
})();

// Poll attention counts without marking hidden results as read.
(() => {
 const dots=document.querySelectorAll('[data-notice-key]');
 if (!dots.length) return;
 let busy=false;
 async function refreshNotices() {
  if (document.hidden || busy) return;
  busy=true;
  try {
   const response=await fetch('/notifications/status',{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
   if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
   const data=await response.json();
   dots.forEach(dot => { dot.hidden=!(Number(data.counts?.[dot.dataset.noticeKey])>0); });
  } catch (_) {} finally { busy=false; }
 }
 window.setInterval(refreshNotices,30000);
 window.addEventListener('focus',refreshNotices);
 document.addEventListener('visibilitychange',refreshNotices);
})();
