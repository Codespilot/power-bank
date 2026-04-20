def get_import_column_mapping():
    return {
        "订单ID": "order_no",
        "支付/退款时间": "order_date",
        "账单月份": "bill_month",
        "账单日期": "bill_date",
        "订单类型": "order_type",
        "订单金额": "order_amount",
        "门店名称": "merchant_name",
        "门店id": "merchant_id",
        "租借费用门店分润金额": "merchant_profit",
        "租借费用代理分润金额": "agent_profit",
    }
