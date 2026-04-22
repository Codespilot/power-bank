// 订单管理页面 JS
function fetchOrders(page) {
  // 获取搜索参数
  const kw = document.getElementById('order-search').value.trim();
  const dateStart = document.getElementById('order-date-start').value;
  const dateEnd = document.getElementById('order-date-end').value;
  const params = new URLSearchParams({page, kw, date_start: dateStart, date_end: dateEnd});
  fetch(`/api/orders?${params}`)
    .then(r=>r.json())
    .then(renderOrderTable);
}


function renderOrderTable(data) {
  // data: {results: [...], count: int, page: int, page_size: int}
  const tbody = document.getElementById('order-table-body');
  tbody.innerHTML = '';
  for(const row of data.results) {
    tbody.innerHTML += `<tr>` +
      `<td>${row.order_date||''}</td>`+
      `<td>${row.bill_month||''}</td>`+
      `<td>${row.bill_date||''}</td>`+
      `<td>${row.order_type||''}</td>`+
      `<td>${row.is_capped?'是':'否'}</td>`+
      `<td>${row.order_amount||''}</td>`+
      `<td>${row.merchant_name||''}</td>`+
      `<td>${row.merchant_profit||''}</td>`+
      `<td>${row.agent_profit||''}</td>`+
      `</tr>`;
  }
  renderOrderPagination(data.count, data.page, data.page_size);
}

function renderOrderPagination(count, page, page_size) {
  let html = '';
  const total = Math.ceil(count/page_size);
  for(let i=1;i<=total;i++) {
    html += `<button class='order-btn order-btn-page' onclick='fetchOrders(${i})' ${page==i?'style=\"background:#2f6fed;color:#fff\"':''}>${i}</button>`;
  }
  document.getElementById('order-pagination').innerHTML = html;
}

function showImportDialog() {
  // 打开导入弹窗
  const dlg = document.getElementById('order-dialog');
  dlg.innerHTML = `<div class='order-dialog-card'>
    <span class='order-dialog-close' onclick='closeDialog()'>&times;</span>
    <h3>导入订单</h3>
    <form id='import-form'>
      <input type='file' name='file' accept='.xls,.xlsx' required>
      <div class='order-dialog-actions'>
        <button type='submit' class='order-btn order-btn-primary'>上传</button>
        <button type='button' class='order-btn' onclick='closeDialog()'>取消</button>
      </div>
    </form>
    <div id='import-error' class='order-dialog-error'></div>
  </div>`;
  dlg.style.display = '';
  document.getElementById('import-form').onsubmit = function(e){
    e.preventDefault();
    const fd = new FormData(this);
    fetch('/api/order-imports/', {
      method:'POST',
      headers: {'X-CSRFToken': window.getCsrfToken ? window.getCsrfToken() : ''},
      credentials: 'same-origin',
      body:fd
    })
      .then(r=>r.json()).then(res=>{
        if(res.id){ closeDialog(); fetchOrders(1); }
        else document.getElementById('import-error').innerText = res.message||'导入失败';
      });
  };
}

function closeDialog() {
  document.getElementById('order-dialog').style.display = 'none';
}

// 导入任务数
function fetchImportTaskCount() {
  fetch('/api/order-imports/running-count/')
    .then(r=>r.json())
    .then(res=>{
      document.getElementById('import-task-count').innerText = `${res.count||0} 个导入任务运行中`;
    });
}

window.onload = function() {
  fetchOrders(1);
  fetchImportTaskCount();
};
