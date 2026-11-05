from tools.mock_api import ReimbursementDocument, Employee, get_employee_info

CITY_LEVELS = {
    "一线": ["北京", "上海", "广州", "深圳", "北上广深"],
    "省会": ["杭州", "南京", "成都", "武汉", "西安", "长沙", "郑州", "济南", "沈阳", "福州", "厦门"],
}

HOTEL_STANDARDS = {
    "总经理": {"一线": 600, "省会": 500, "其他": 400},
    "经理": {"一线": 450, "省会": 380, "其他": 300},
    "员工": {"一线": 300, "省会": 250, "其他": 200},
}

MEAL_STANDARDS = {
    "一线": 100,
    "省会": 80,
    "其他": 60,
}

ENTERTAINMENT_STANDARDS = {
    "总经理": 2000,
    "经理": 1000,
    "员工": 500,
}

CITY_KEYWORD_MAP = {
    "北京": "一线", "上海": "一线", "广州": "一线", "深圳": "一线",
    "杭州": "省会", "南京": "省会", "成都": "省会", "武汉": "省会",
    "西安": "省会", "长沙": "省会", "郑州": "省会", "济南": "省会",
    "沈阳": "省会", "福州": "省会",
}


def detect_city_level(desc: str) -> str:
    for city, level in CITY_KEYWORD_MAP.items():
        if city in desc:
            return level
    return "其他"


def check_hotel_standard(doc: ReimbursementDocument, emp: Employee) -> list[str]:
    issues = []
    hotel_amount = 0
    hotel_desc = ""
    days = 3

    for item in doc.items:
        if "住宿" in item.category or "酒店" in item.category:
            hotel_amount = item.amount
            hotel_desc = item.desc
            if "天" in hotel_desc:
                try:
                    days = int(hotel_desc.split("天")[0].replace("天", "").strip()[-1])
                except (ValueError, IndexError):
                    pass

    if hotel_amount == 0:
        return issues

    daily_avg = hotel_amount / days
    city_level = detect_city_level(hotel_desc)
    standard = HOTEL_STANDARDS.get(emp.level, HOTEL_STANDARDS["员工"])
    max_daily = standard.get(city_level, standard["其他"])

    if daily_avg > max_daily:
        issues.append(
            f"住宿超标: 日均 ¥{daily_avg:.0f} > 标准 ¥{max_daily} ({city_level}城市 {emp.level}级别)"
        )
    return issues


def check_meal_standard(doc: ReimbursementDocument, emp: Employee) -> list[str]:
    issues = []
    meal_amount = 0
    meal_desc = ""
    days = 3

    for item in doc.items:
        if "餐饮" in item.category or "伙食" in item.category:
            meal_amount += item.amount
            meal_desc = item.desc

    if meal_amount == 0:
        return issues

    if "补贴" in meal_desc:
        city_level = "其他"
        for item in doc.items:
            for city, level in CITY_KEYWORD_MAP.items():
                if city in item.desc and "交通" not in item.category:
                    city_level = level
                    break

        if "天" in meal_desc:
            try:
                days = int(meal_desc.split("天")[0][-1])
            except (ValueError, IndexError):
                pass

        daily_avg = meal_amount / days
        max_daily = MEAL_STANDARDS.get(city_level, MEAL_STANDARDS["其他"])

        if daily_avg > max_daily + 20:
            issues.append(
                f"补贴超标: 日均 ¥{daily_avg:.0f} > 标准 ¥{max_daily} ({city_level}城市)"
            )
    return issues


def check_entertainment_standard(doc: ReimbursementDocument, emp: Employee) -> list[str]:
    issues = []
    if "招待" not in doc.type:
        return issues

    max_amount = ENTERTAINMENT_STANDARDS.get(emp.level, ENTERTAINMENT_STANDARDS["员工"])
    if doc.amount > max_amount:
        issues.append(
            f"招待费超标: ¥{doc.amount:,.0f} > 标准 ¥{max_amount:,} ({emp.level}级别)"
        )
    return issues


def check_city_transport(doc: ReimbursementDocument) -> list[str]:
    issues = []
    transport_amount = 0
    days = 3

    for item in doc.items:
        if "市内" in item.desc or "打车" in item.desc or "地铁" in item.desc:
            transport_amount += item.amount

    if transport_amount == 0:
        return issues

    if "高铁" not in doc.type and "出差" not in doc.type:
        return issues

    daily_avg = transport_amount / days
    if daily_avg > 70:
        issues.append(
            f"市内交通偏高: 日均 ¥{daily_avg:.0f} > 建议 ¥50/天"
        )
    return issues


def verify_document(doc: ReimbursementDocument) -> dict:
    result = {
        "doc_id": doc.doc_id,
        "employee": doc.employee,
        "check_status": "通过",
        "issues": [],
        "suggestions": [],
        "summary": "",
    }

    emp = get_employee_info(doc.employee)
    if not emp:
        result["check_status"] = "信息不全"
        result["issues"].append(f"员工信息未找到")
        result["summary"] = "员工信息不存在，无法进行核对"
        return result

    all_issues = []
    all_issues.extend(check_hotel_standard(doc, emp))
    all_issues.extend(check_meal_standard(doc, emp))
    all_issues.extend(check_entertainment_standard(doc, emp))
    all_issues.extend(check_city_transport(doc))

    if all_issues:
        result["check_status"] = "需关注"
        result["issues"] = all_issues
        result["suggestions"] = [
            "请对照报销制度检查各项费用是否超标",
            "超标部分需特别说明原因并经上级批准",
            "住宿超标需补充特别审批单",
        ]
    else:
        result["check_status"] = "通过"
        result["summary"] = "单据核对通过，各项费用符合公司报销标准"

    return result


def format_verify_result(result: dict) -> str:
    lines = []
    lines.append(f"===== 财务核对结果 =====")
    lines.append(f"单据号: {result['doc_id']}")
    lines.append(f"申请人: {result['employee']}")
    lines.append(f"核对状态: {result['check_status']}")

    if result["issues"]:
        lines.append("\n⚠️ 发现问题:")
        for issue in result["issues"]:
            lines.append(f"  • {issue}")

    if result["suggestions"]:
        lines.append("\n💡 整改建议:")
        for sug in result["suggestions"]:
            lines.append(f"  • {sug}")

    if result["summary"]:
        lines.append(f"\n✅ {result['summary']}")

    return "\n".join(lines)
