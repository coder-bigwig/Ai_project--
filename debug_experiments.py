"""检查实验数据"""
import requests
import json

API_URL = "http://localhost:8001"

print("获取所有实验...")
res = requests.get(f"{API_URL}/api/experiments")
experiments = res.json()

print(f"\n找到 {len(experiments)} 个实验:\n")
for exp in experiments:
    print(f"ID: {exp['id']}")
    print(f"  标题: {exp['title']}")
    print(f"  创建者: {exp.get('created_by', '无')}")
    print(f"  发布状态: {exp.get('published', '无')}")
    print()

print("\n检查 teacher_001 的课程...")
res2 = requests.get(f"{API_URL}/api/teacher/courses?teacher_username=teacher_001")
teacher_courses = res2.json()
print(f"教师课程数: {len(teacher_courses)}")

if len(teacher_courses) == 0:
    print("\n⚠️  问题：teacher_001 没有课程！")
    print("检查创建者字段...")
    for exp in experiments:
        creator = exp.get('created_by', '')
        print(f"  '{creator}' == 'teacher_001' ? {creator == 'teacher_001'}")
