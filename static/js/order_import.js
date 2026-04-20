layui.use(function () {
  var table = layui.table;
  var laydate = layui.laydate;
  var upload = layui.upload;
  var form = layui.form;
  var layer = layui.layer;

  function statusBadge(status) {
    switch (status) {
      case 1:
        return '<span class="layui-badge layui-bg-gray">未开始</span>';
      case 2:
        return '<span class="layui-badge layui-bg-blue">运行中</span>';
      case 3:
        return '<span class="layui-badge layui-bg-green">成功</span>';
      case 4:
        return '<span class="layui-badge">失败</span>';
      default:
        return '<span class="layui-badge-rim">未知</span>';
    }
  }

  laydate.render({
    elem: '#import-date-range',
    range: ['#import-date-start', '#import-date-end'],
    rangeLinked: true
  });

  table.render({
    elem: '#import-list',
    id: 'import-list',
    url: '/api/order-imports/',
    method: 'get',
    page: true,
    limits: [10, 20, 50],
    limit: 10,
    height: 'full-300',
    request: {
      pageName: 'page',
      limitName: 'page_size'
    },
    response: {
      statusCode: 200
    },
    parseData: function (res) {
      return {
        code: 200,
        msg: res.message || '',
        count: res.count || 0,
        data: res.results || []
      };
    },
    cols: [[
      { field: 'file_name', title: '文件名', minWidth: 260 },
      { field: 'succeed_rows', title: '成功行数', width: 120, templet: function (d) { return d.succeed_rows || 0; } },
      { field: 'failed_rows', title: '失败行数', width: 120, templet: function (d) { return d.failed_rows || 0; } },
      { field: 'status', title: '状态', width: 120, templet: function (d) { return statusBadge(d.status); } },
      { field: 'created_at', title: '创建时间', minWidth: 180 }
    ]]
  });

  form.on('submit(import-search)', function (data) {
    table.reload('import-list', {
      page: { curr: 1 },
      where: data.field
    });
    return false;
  });

  document.getElementById('refresh-import-btn').addEventListener('click', function () {
    table.reload('import-list', {
      page: { curr: 1 }
    });
  });

  upload.render({
    elem: '#import-order-btn',
    url: '/api/order-imports/',
    accept: 'file',
    exts: 'xls|xlsx',
    headers: {
      'X-CSRFToken': window.getCsrfToken ? window.getCsrfToken() : ''
    },
    done: function (res) {
      if (res.id) {
        layer.msg('上传成功，导入任务已创建');
        table.reload('import-list', {
          page: { curr: 1 }
        });
      } else {
        layer.msg(res.message || '导入失败', { icon: 2 });
      }
    },
    error: function () {
      layer.msg('上传失败，请稍后重试', { icon: 2 });
    }
  });
});
