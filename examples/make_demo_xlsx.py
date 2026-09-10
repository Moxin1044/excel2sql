#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一个用于试用 excel2sql 的演示 Excel 文件。

用法：
    python examples/make_demo_xlsx.py demo.xlsx
"""

import random
import sys

from openpyxl import Workbook

SURNAMES = "赵钱孙李周吴郑王冯陈"
GIVEN = "伟芳娜敏静秀丽强磊洋勇艳杰娟涛明超霞平刚桂英"
COMPANIES = ["科技有限公司", "网络科技", "信息技术", "数据服务", "智能科技"]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "demo.xlsx"
    random.seed(2026)

    workbook = Workbook()
    users = workbook.active
    users.title = "用户表"
    users.append(["用户编号", "姓名", "手机号", "身份证号", "余额", "注册日期", "是否VIP", "备注"])
    for index in range(200):
        users.append([
            "U%05d" % index,
            random.choice(SURNAMES) + random.choice(GIVEN),
            "13%d%08d" % (random.randint(0, 9), index),
            "11010119900101%04d" % index,
            round(random.uniform(0, 99999), 2),
            "2024-%02d-%02d" % (random.randint(1, 12), random.randint(1, 28)),
            index % 4 == 0,
            "备注可能包含'引号'或\\反斜杠" if index % 50 == 0 else None,
        ])

    orders = workbook.create_sheet("订单")
    orders.append(["订单号", "用户编号", "金额", "下单时间", "状态"])
    for index in range(500):
        orders.append([
            "SO%08d" % index,
            "U%05d" % random.randint(0, 199),
            round(random.uniform(1, 9999), 2),
            "2024-%02d-%02d %02d:%02d:%02d" % (
                random.randint(1, 12), random.randint(1, 28),
                random.randint(0, 23), random.randint(0, 59), random.randint(0, 59)),
            random.choice(["待支付", "已支付", "已发货", "已完成"]),
        ])

    workbook.save(path)
    print("已生成演示文件：%s（用户表 200 行 / 订单 500 行）" % path)


if __name__ == "__main__":
    main()
