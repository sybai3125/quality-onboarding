"""
JSON 데이터를 quality_onboarding_navigator.db (SQLite)로 만드는 1회용 시드 스크립트.
스키마는 loader.py의 _SCHEMA와 동일하다(진행 상황 테이블 3개 포함).

실행: python build_db.py            -> 같은 폴더에 quality_onboarding_navigator.db 생성
      python build_db.py --force    -> 이미 있는 DB(진행 상황 포함)를 지우고 새로 생성
"""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "quality_onboarding_navigator.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS project_types (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT
);
CREATE TABLE IF NOT EXISTS phases (
    id TEXT PRIMARY KEY,
    project_type_id TEXT NOT NULL REFERENCES project_types(id),
    "group" TEXT, name TEXT NOT NULL, "order" INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY,
    phase_id TEXT NOT NULL REFERENCES phases(id),
    title TEXT NOT NULL, description TEXT,
    repeat_per_phase INTEGER NOT NULL DEFAULT 0,
    remote_support_possible INTEGER NOT NULL DEFAULT 0,
    deliverable_json TEXT, quality_role_json TEXT,
    required_skills_json TEXT, standard_ref_json TEXT
);
CREATE TABLE IF NOT EXISTS glossary (
    id TEXT PRIMARY KEY, term TEXT NOT NULL, definition TEXT
);
CREATE TABLE IF NOT EXISTS progress_checked (activity_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS progress_due_dates (
    activity_id TEXT PRIMARY KEY, due_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS progress_notes (
    id TEXT PRIMARY KEY, activity_id TEXT NOT NULL,
    text TEXT NOT NULL, status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_phases_type ON phases(project_type_id);
CREATE INDEX IF NOT EXISTS idx_activities_phase ON activities(phase_id);
CREATE INDEX IF NOT EXISTS idx_notes_activity ON progress_notes(activity_id);
"""

PROJECT_TYPES = [("new", "신규", "신규 시스템 구축 프로젝트")]

PHASES = [
    ("1-1", "new", "1.수주", "제안", 1),
    ("1-2", "new", "1.수주", "기술협상/계약/착수", 2),
    ("2-1", "new", "2.이행", "분석", 3),
    ("2-2", "new", "2.이행", "설계", 4),
    ("2-3", "new", "2.이행", "구축", 5),
    ("2-4", "new", "2.이행", "테스트", 6),
    ("2-5", "new", "2.이행", "전개(이행)", 7),
    ("2-6", "new", "2.이행", "종료", 8),
]

ACTS = []


def a(id, title, desc, dname, dref, doing, guiding=None, feedback=None,
      skills="", reg=None, meth=None, repeat=False, remote=False):
    ACTS.append({
        "id": id,
        "phase_id": id.rsplit("-", 1)[0],
        "title": title,
        "description": desc,
        "repeat_per_phase": repeat,
        "remote_support_possible": remote,
        "deliverable": {"name": dname, "input_ref": dref},
        "quality_role": {"guiding": guiding, "doing": doing, "feedback": feedback},
        "required_skills": [s for s in skills.split("|") if s],
        "standard_ref": {"regulation": reg, "methodology": meth},
    })


# ---- 1-1 제안 ----
a("1-1-1", "RFP 품질 요구사항 확인 및 제안 반영", "RFP 품질 요구사항 및 상세 내용을 파악하여 이를 제안 목차 및 내용에 반영한다.", "제안서 - 품질관리 방안, 테스트 수행 방안 등", "RFP 품질 요구사항", "QE", skills="품질일반 지식")
a("1-1-2", "전사 규정 및 표준/가이드 확인 및 제안 반영", "전사 프로세스에 따른 프로젝트 이행을 할수 있도록 전사 규정 및 표준/가이드를 제안에 반영하고 확인 한다.", "제안서 - 관리방법론, 개발방법론 ", "프로젝트 이행 규정\nSW 개발 규정\n표준 프로세스", "QE", skills="SW공학 프로세스")
a("1-1-3", "개발 방법론 경로 선정 및 테일러링", "프로젝트 특성 및 고객 요구사항에 따른 개발망법론을 선정하여 테일러링 하여 제안한다.", "제안서 - 개발방법론", "프로젝트 및 구축 시스템 범위에 따른 특성 및 RFP 요구사항\n데이터 전환, 연계 시스템 등 고려사항", "QE", skills="SW공학 프로세스")
a("1-1-4", "경로별 산출물 정의", "선정된 방법론의 각 경로별 산출물을 정의 한다.", "제안서 - 경로별 수행 절차 및 산출물", "방법론\nRFP 품질 요구사항\n프로젝트 개발 특성", "QE", skills="CM")
a("1-1-5", "품질보증 방안 수립", "프로젝트 품질 보증 활동 및 일정을 수립한다.", "제안서 - 품질보증 방안", "RFP 품질 요구사항\n사내표준, 규정", "QE", skills="V&V")
a("1-1-6", "프로젝트 관리도구 활용 정의(PMS-F, Smart Orchestra, 테스팅 도구 등)", "프로젝트 관리도구를 선정하고, 활동 방안을 정의한다.\n- 본사 제공 도구 이외 RFP 요구사항에 따른 도구 선정 및 활용안은 제안 팀 내 협의하여 진행한다.", "제안서 - 프로젝트 관리 도구 활용 정의", "RFP 품질 요구사항\n사내표준, 규정", "QE", skills="프로젝트/품질관리도구")
a("1-1-7", "범위,공정,자원에 따른 일정 수립\n  - Task간의 의존성 도출(CP의 적합성 검토)", "범위,공정,자원에 따른 프로젝트 일정을 수립한다.", "제안서 - 공정도, 프로젝트 마일스톤 및 일정, CP", "프로젝트 범위\n방법론\n투입인력", "QE\nOther", feedback="QE", skills="V&V")

# ---- 1-2 기술협상/계약/착수 ----
a("1-2-1", "프로젝트 이행 전략 워크샵 사전 준비_제안서 기반 품질전략 수립", "이행전략 워크샵 진행을 위한 품질 전략을 수립한다.\n - 각 영역별 범위, 방안 및 일정을 수립\n - 제안/이행 인력이 상이한 경우 담당자간 인수인계 실시", "품질전략 수립\n마일스톤/WBS (CP 확인)", "제안서\n수주진단시 도출된 리스크\n프로젝트 이행규정", "QE", skills="법/제도|전사규정", reg="O")
a("1-2-2", "프로젝트 이행 전략 워크샵 참여_품질목표 상세화", "프로젝트 목표 달성을 위한 역할자별 목표와 상세 수행방안을 달성 여부 판단 가능한 수준으로 작성 한다.", "프로젝트이행전략 워크샵 결과 합의서", "프로젝트 품질 목표\n핵심이행이력 R&R", "QE", skills="법/제도|전사규정", reg="O")
a("1-2-3", "프로젝트목표 합의서_품질영역 Sign-off ", "프로젝트 이행전략 워크샵을 통해 작성된 프로젝트 목표에 핵심 이행인력들이 참여하여 합의한다.", "수기 Sign", "프로젝트이행전략 워크샵 결과 합의서", "QE", skills="법/제도|전사규정", reg="O")
a("1-2-4", "이해관계자와 품질 협의를 위한 채널 확보", "고객(PM, 품질담당자 등), 외부 PMO, 상주 감리, 수행사 프로젝트팀(영역별 핵심 담당자 PL 등)의 품질관련 이해관계자를 파악하고 협의를 위한 채널을 확보 한다.", "품질 협의 채널 \n(협의체, 의사소통 계획 등)", "프로젝트 수행 조직도\n인터뷰", "QE", skills="품질일반 지식")
a("1-2-5", "프로젝트 표준 수립 (기준서, 산출물 표준 양식, 문서 표준 등)", "프로젝트에 적용할 작업방식과 산출물의 일관성을 확보하여 재 작업을 최소화하고 의사소통을 명확하게 하기위하여 프로젝트 표준을 수립한다.", "프로젝트 표준 프로세스\n프로세스 테일러링 결과서\n문서관리 지침서\n프로젝트 산출물 목록\n산출물 표준 양식", "프로젝트 범위관련 문서\n제안서", "QE", skills="SW공학 프로세스", meth="O", remote=True)
a("1-2-6", "공정 테일러링 및 WBS 작성", "프로젝트 공정 테일러링 및 WBS를 확정한다.", "프로젝트 공정도\nWBS", "프로젝트 범위관련 문서\n제안서", "QE\nOther", guiding="QE", feedback="QE", skills="SW공학 프로세스")
a("1-2-7", "프로젝트 관리 도구 확정 및 설치(pms-F 등)", "프로젝트 관리도구를 확정/설치 하고 프로젝트에 맞게 환경을 설정한다.", "프로젝트 관리 도구 설치", "프로젝트 범위관련 문서\n제안서", "Other", feedback="QE", skills="SW공학 프로세스", remote=True)
a("1-2-8", "품질목표 설정 및 지표 정의", "프로젝트의 품질지표를 정의하고 각 지표 별 목표수준 설정을 통하여 일정한 품질을 유지하기 위한 지속적인 실적 분석과 관리의 기준을 정의 한다.", "품질 목표 수립\n - 품질 요구사항 도출\n - 프로젝트에 적용할 품질 지표 선정\n - 품질지표 별 목표수준 설정\n", "제안요청서\n제안서\n계약서\n프로젝트 범위 관련 문서", "QE", guiding="QE", skills="SW지표, 측정/분석", meth="O", remote=True)
a("1-2-9", "품질 보증 계획 수립", "분석, 설계, 구축, 시험, 전개에 이르는 프로젝트 전 과정에 걸쳐 체계적으로 품질 보증 활동을 실행하고 품질목표를 달성하기 위하여 프로젝트의 품질 보증 계획을 수립한다.", "품질보증 계획서\n - 품질보증 조직 및 자원 결정\n - 품질보증 전략/절차 수립\n - 산출물 검토계획 수립 \n - 테스트 계획 수립\n - 프로젝트 외부조직의 감리 및 내부감사 계획 수립", "제안서\n계약서\n품질목표", "QE", skills="V&V", meth="O")
a("1-2-10", "측정 계획 수립", "프로젝트의 가시성을 제공할 수 있는 적절한 지표를 정의하고 수집주기를 정의하여 효과적으로 측정활동이 이루어 지도록 한다.", "측정계획서", "품질 목표", "QE", skills="SW지표, 측정/분석", remote=True)
a("1-2-11", "형상관리 계획 수립(변경관리 포함)", "형상항목을 식별하고 형상항목의 변경통제, 모니터링 및 감사 활동을 통해 무결성이 확보되고 유지하기 위한 계획을 작성한다", "형상관리 계획서\n변경관리 계획서", "산출물 목록 ,개발환경", "QE", skills="CM", remote=True)
a("1-2-12", "관리/개발 영역별 단계별 산출물 템플릿 정의", "개발 영역/단계별 Task에 정의된 산출물에 대한 템플릿 초안을 정의한다. 정의된 템플릿은 필요 시 각 단계 수행 전 정련하여 사용한다.", None, None, "QE\nOther", guiding="QE", feedback="QE", skills="SW공학 프로세스", remote=True)
a("1-2-13", "프로젝트 착수 교육(표준/가이드, 양식 등)", "프로젝트 수행을 위한 기본사항인 프로젝트 표준(방법론, 개발표준 및 가이드, 프로세스 등) 과 품질보증 활동에 대하여 프로젝트 수행인원이 이해하고 표준대로 이행할 수 있도록 한다.", "교육결과서", "프로젝트 착수 교육 교재", "QE", skills="SW공학 프로세스", meth="O", remote=True)
a("1-2-14", "프로젝트 범위, R&R 검토 및 확정 (고객/내부)\n  - 사업수행계획서 작성 및 제출", "프로젝트 범위 및 수행 R&R을 확정 및 검토하여 고객 제출한다.", "사업수행계획서\n범위기술서", "제안서\n협상결과", "QE\nOther", feedback="QE", skills="SW공학 프로세스")

# ---- 2-1 분석 ----
a("2-1-1", "프로젝트 관리 필수 지표 정의 및 목표 설정", "프로젝트 관리 지표를 정의하고 합의한다.", "프로젝트 관리지표\n측정계획서", "사업수행계획서", "QE\nOther", guiding="QE", feedback="QE", skills="SW지표, 측정/분석", reg="O")
a("2-1-2", "프로젝트 WBS 집계, 통합 및 등록", "각 영역별 작성한 WBS를 통합하여 pms-F에 등록한다.", None, None, "QE", skills="SW공학 프로세스", remote=True)
a("2-1-3", "프로젝트 일정(Task 정의/인력/일정 수립 및 진척) 관리", "프로젝트 전체 일정에 대한 주별 실적 입력 및 진척관리를 수행한다.", "주별 진척 / 보고", "주별 실적 진척률", "Other", feedback="QE", skills="SW공학 프로세스")
a("2-1-4", "분석단계 산출물 작성 가이드", "분석단계 대상 산출물 가이드를 작성하고, 각 대상자에게 가이드 한다.", "교육결과서", "분석단계 산출물 작성 가이드", "QE", skills="SW공학 프로세스", remote=True)
a("2-1-5", "분석 산출물 작성 가이드(모델링 등) 검토(해당 담당자가 가이드 교육 진행)", "프로젝트 방법론에 따른 각 담당영역별로 가이드를 작성하고 적정하게 작성되는지 검토한다.", "검토결과서", "분석모델링가이드 등", "Other", guiding="QE", feedback="QE", skills="SW공학 프로세스")
a("2-1-6", "총괄 테스트 계획 수립", "총괄테스트 계획을 수립하여  프로젝트 전반에 걸친 테스트 활동을 계획하고 합의한다.", "총괄테스트계획서", "사업수행계획서\n품질보증계획서\n요구사항정의서", "QE\nOther", guiding="QE", feedback="QE", skills="V&V", remote=True)
a("2-1-7", "리뷰 계획 수립 : 분석단계에 리뷰 그룹 설정, 대상, 주기, 방법 등 정의", "분석단계 리뷰 계획을 수립하고 공유 한다.", "분석단계 품질검토 계획서", "품질보증계획서", "QE", skills="법/제도|전사규정", reg="O")
a("2-1-8", "일괄도급이 포함된 경우, 도급 검수 일정 계획 수립, 품질 목표 정의(이행 PM 협업)", "도급 영역의 검수일정 계획 수립 및 품질 목표를 정의한다.", "도급계약서", "사업수행계획서\n계약서", "Sub", feedback="QE", skills="법/제도|전사규정", reg="O", remote=True)
a("2-1-9", "일괄도급이 포함된 경우, 도급 품질 계획 검토", "전사규정에 부합하도록 도급 품질검토계획을 도급업체에 작성 요청하고 겁토한다.", "검토결과서\n도급계약서", "도급 품질검토계획서", "Other", feedback="QE", skills="법/제도|전사규정", reg="O", remote=True)
a("2-1-10", "일괄도급이 포함된 경우, 도급 품질 점검 결과 관리 및 결과서 업체 송부", "도급영역 수행에서 수행한 품질점검 결과를 검토하고 결과를피드백 한다.", "검토 결과서", "도급영역 품질검토 결과서", "QE", skills="법/제도|전사규정", reg="O", remote=True)
a("2-1-11", "공정 관리(Smart Orchestra) 도구 설치 및 교육(기준정보 SetUp 활동 포함)", "공정관리 도구를 설치하고 사용 가이드를 수행한다. \n - 분석단계 기능을 사용하지 않는 경우 설계 이후 설치 및 셋업함 \n - 규모에 따라 본사 지원팀의 지원 가능", "도구 설치\n사용가이드", "사업수행계획서", "Other", feedback="QE", skills="프로젝트/품질관리도구", reg="O", remote=True)
a("2-1-12", "주단위 수집된 프로젝트 지표 기반 분석 / 품질평가/ 시정조치", "주단위 지표를 수집하고 입력한다.", "주단위 지표 입력", "측정계획서", "QE\nOther", feedback="QE", skills="법/제도|전사규정|SW지표, 측정/분석", reg="O", meth="O")
a("2-1-13", "분석단계 결함 및 시정조치 관리(결함 집계, 피드백 및 조치결과 확인)", "분석 단계 시 발생되는 결함에 대하여 집계, 검토 후 피드백, 시정조치 결과 확인 업무를 수행한다.", "주간보고서 \n수시보고서", "결함등록 현황", "QE", skills="V&V")
a("2-1-14", "분석단계 결함 발생 원인 분석, 재발 방지책 수립 및 이행", "도출된 결함에 대해 조치 계획을 수립하고, 계획에 따라 조치 수행한다.", "검토결과서", "검토결과서", "QE\nOther", feedback="QE", skills="V&V")
a("2-1-15", "분석단계말 품질지표 측정 (정성/정량)\n  - 범위 증감  확인, 생산성 등 필수지표", "분석단계말 품질지표를 측정하고 분석한다.", "분석단계말 지표 측정결과", "품질보증계획서\n측정계회서", "QE", skills="SW지표, 측정/분석")
a("2-1-16", "분석단계 산출물 리뷰 : 요구사항 도출 적정성 검토", "기술된 요구사항 정의서의 내역이 고객의 요구사항을 모두 기술하였는지에 대한 완전성 및 정확성에 대한 검토를 수행한다.", "검토결과서", "요구사항정의서", "QE\nOther", feedback="QE", skills="SW공학 프로세스", reg="O", remote=True)
a("2-1-17", "분석단계 산출물 리뷰\n  - 표준준수\n  - 상세화 및 적합성 검토", "분석단계 산출물 검토계획에따라 Task별 작성 산출물에 대한 검토를 수행한다.", "검토결과서", "분석단계 산출물", "QE", skills="V&V", remote=True)
a("2-1-18", "분석단계 요구사항 추적 내용 검토 및 확인", "프로젝트의 범위와 고객의 요구사항을 관리하는 활동으로 요구사항과 각 스테이지의 산출물을 검토하여 요구사항 추적 매트릭스를 작성하여, 고객과 합의된 요구사항을 추적 및 검증하도록 한다", "검토결과서", "요구사항추적매트릭스\n사업수행계획서/범위기술서", "QE\nOther", feedback="QE", skills="V&V")
a("2-1-19", "분석단계말 검토(리뷰 Sampling)\n  - QA 승인\n  - 고객 승인", "분석단계 작성 및 보완된 산출물에 대해 단계말에 최종 검토를 수행하고 이를 보완하여 제출한다.", "검토결과서", "분석단계 산출물", "QE\nOther", feedback="QE", skills="V&V", reg="O", remote=True)
a("2-1-20", "분석단계말 산출물 Baseline 수립\n  - 형상감사 포함", "분석단계말 제출되고 고객 승인이 완료된 산출물에 대해 Baseline을 수립한다.\n  - 사전에 형상감사를 통해 구성항목의 정확성, 완전성, 무결성을 확인\n  - 다음단계 변경관리를 위한 기준선을 설정", "형상감사보고서 (Optional)", "분석단계 승인산출물", "QE", skills="CM")

# ---- 2-2 설계 ----
a("2-2-1", "설계 산출물 작성 가이드", "설계단계 대상 산출물 가이드를 작성하고, 각 대상자에게 가이드 한다.", "교육결과서", "설계단계 산출물 작성 가이드", "QE", skills="SW공학 프로세스", remote=True)
a("2-2-2", "설계 산출물 작성 가이드(설계모델링, 아키, 화면 등) 검토(해당 담당자가 가이드 교육 진행)", "프로젝트 방법론에 따른 각 담당영역별로 가이드를 작성하고 적정하게 수행되는지 검토한다.", "검토결과서", "설계모델링가이드 등", "Other", guiding="QE", feedback="QE", skills="SW공학 프로세스")
a("2-2-3", "설계서 작성 진척 모니터링 / 관리\n  - 작성 계획 대비 실적", "설계 산출물 작성 진척을 관리한다.", "진척관리대장(공정관리시스템)\n진척 집계표", "설계 산출물", "Other", guiding="QE", feedback="QE", skills="SW지표, 측정/분석")
a("2-2-4", "통합 테스트 계획 수립", "통합테스트 계획을 수립하고 합의한다.", "통합테스트 계획서", "사업수행계획서\n품질보증계획서\n요구사항정의서", "QE\nOther", guiding="QE", feedback="QE", skills="V&V")
a("2-2-5", "단위 테스트 계획 수립", "단위테스트 계획을 수립하고 합의한다.", "단위테스트 계획서", "사업수행계획서\n품질보증계획서\n요구사항정의서", "QE\nOther", guiding="QE", feedback="QE", skills="V&V")
a("2-2-6", "일괄도급이 포함된 경우, 도급 품질 점검 결과 관리 및 결과서 업체 송부", "도급영역 수행에서 수행한 품질점검 결과를 검토하고 결과를피드백 한다.", "검토 결과서", "도급영역 품질검토 결과서", "QE", skills="법/제도|전사규정", reg="O", repeat=True, remote=True)
a("2-2-7", "주단위 수집된 프로젝트 지표에 대한  분석 / 품질평가/ 시정조치", "주단위 지표를 수집하고 입력한다.", "주단위 지표 입력", "측정계획서", "QE\nOther", feedback="QE", skills="법/제도|전사규정|SW지표, 측정/분석", reg="O", meth="O", repeat=True)
a("2-2-8", "설계단계 산출물 리뷰\n  - 표준준수\n  - 상세화 및 적합성 검토", "설계단계 산출물 검토계획에따라 Task별 작성 산출물에 대한 검토를 수행한다.", "검토결과서", "설계단계 산출물", "QE", skills="V&V", repeat=True, remote=True)
a("2-2-9", "설계단계 결함 및 시정조치 관리(결함 집계, 피드백 및 조치결과 확인)", "설계 단계 시 발생되는 결함에 대하여 집계, 검토 후 피드백, 시정조치 결과 확인 업무를 수행한다.", "주간보고서 \n수시보고서", "결함등록 현황", "QE", skills="V&V", repeat=True)
a("2-2-10", "설계단계 결함 발생 원인 분석, 재발 방지책 수립 및 이행", "도출된 결함에 대해 조치 계획을 수립하고, 계획에 따라 조치 수행한다.", "검토결과서", "검토결과서", "QE\nOther", feedback="QE", skills="V&V", repeat=True)
a("2-2-11", "설계단계말 품질지표 측정 (정성/정량)\n  - 범위 증감  확인, 생산성 등 필수지표", "설계단계말 품질지표를 측정하고 분석한다.", "분석단계말 지표 측정결과", "품질보증계획서\n측정계회서", "QE", skills="SW지표, 측정/분석", repeat=True)
a("2-2-12", "설계단계 요구사항 추적 내용 검토 및 확인", "프로젝트의 범위와 고객의 요구사항을 관리하는 활동으로 요구사항과 각 스테이지의 산출물을 검토하여 요구사항 추적 매트릭스를 작성하여, 고객과 합의된 요구사항을 추적 및 검증하도록 한다", "검토결과서", "요구사항추적매트릭스\n사업수행계획서/범위기술서", "QE\nOther", feedback="QE", skills="V&V", repeat=True)
a("2-2-13", "설계단계말 검토(리뷰 Sampling)\n  - QA 승인\n  - 고객 승인", "설계단계 작성 및 보완된 산출물에 대해 단계말에 최종 검토를 수행하고 이를 보완하여 제출한다.", "검토결과서", "분석단계 산출물", "QE\nOther", feedback="QE", skills="V&V", reg="O", repeat=True, remote=True)
a("2-2-14", "설계단계말 산출물 Baseline 수립\n  - 형상감사 포함", "설계단계말 제출되고 고객 승인이 완료된 산출물에 대해 Baseline을 수립한다.\n  - 사전에 형상감사를 통해 구성항목의 정확성, 완전성, 무결성을 확인\n  - 다음단계 변경관리를 위한 기준선을 설정", "형상감사보고서 (Optional)", "설계단계 승인산출물", "QE", skills="CM", repeat=True)

# ---- 2-3 구축 ----
a("2-3-1", "구축 산출물 작성 가이드", "구축단계 산출물에 대한 작성법을 정리하여 문서화한 후 해당 내용을 구성원에게 교육한다.", "테스트 산출물 작성 가이드 및 교육자료", "총괄테스트계획서\n단위테스트계획서", "QE", skills="SW공학 프로세스", remote=True)
a("2-3-2", "개발 가이드(코딩표준/주석, 보안 등) 검토(해당 담당자가 가이드 교육 진행)", "프로젝트 방법론에 따른 각 담당영역별로 가이드를 적정하게 수행되는지 검토한다.", "검토결과서", "분석모델링가이드", "Other", guiding="QE", feedback="QE", skills="SW공학 프로세스")
a("2-3-3", "개발 및 단위테스트 진척 모니터링 / 관리\n  - 프로그램 개발 계획 대비 실적\n  - 단위테스트 케이스 수행 계획 및 실적", "개발 및 단위테스트 진척 모니터링을 수행한다.\n  - 프로그램 개발 계획 대비 실적\n  - 단위테스트 케이스 수행 계획 및 실적", "진척관리대장", "개발 / 단테 실적", "Other", guiding="QE", feedback="QE", skills="SW공학 프로세스")
a("2-3-4", "개발 생산성 분석", "프로젝트 개발 생산성 분석을 진행한다.", "생선성 분석결과", "규모, 공수", "QE", skills="SW지표, 측정/분석", remote=True)
a("2-3-5", "일괄도급이 포함된 경우, 도급 품질 점검 결과 관리 및 결과서 업체 송부", "도급영역 수행에서 수행한 품질점검 결과를 검토하고 결과를피드백 한다.", "점검 결과서", "도급영역 품질검토 결과서", "QE", skills="법/제도|전사규정", reg="O", repeat=True, remote=True)
a("2-3-6", "주단위 수집된 프로젝트 지표에 대한 분석 / 품질평가/ 시정조치", "주단위 지표를 수집하고 입력한다.", "주단위 지표 입력", "측정계획서", "QE\nOther", feedback="QE", skills="법/제도|전사규정|SW지표, 측정/분석", reg="O", meth="O", repeat=True)
a("2-3-7", "구축단계 결함 및 시정조치 관리(결함 집계, 피드백 및 조치결과 확인)", "구축 단계 시 발생되는 결함에 대하여 집계, 검토 후 피드백, 시정조치 결과 확인 업무를 수행한다.", "주간보고서 \n수시보고서", "결함등록 현황", "QE", skills="V&V", repeat=True)
a("2-3-8", "구축단계 결함 발생 원인 분석, 재발 방지책 수립 및 이행", "구축 단계 시 발생결함 중 주요 결함에 대한 원인 분석 및 재발 방지책을 수립하고 이행한다.", "결함보고서\n(원인분석/재발방지 측면)", "구축단계 발생 결함", "QE\nOther", feedback="QE", skills="V&V", repeat=True)
a("2-3-9", "구축단계말 품질지표 측정 (정성/정량)\n  - 범위 증감  확인, 생산성 등 필수지표", "구축 단계말 정성/정량 품질지표를 측정한다.", "측정보고서", "변경요청서", "QE", skills="SW지표, 측정/분석", repeat=True)
a("2-3-10", "구축단계 산출물 리뷰\n  - 표준준수\n  - 상세화 및 적합성 검토", "구축 단계 산출물 대상으로 리뷰를 수행한다. ", "검토결과서", "전개단계 산출물", "QE", skills="V&V", repeat=True, remote=True)
a("2-3-11", "개발 프로그램 QA 테스트 (Sampling)", "QE가 직접 제3자 단위테스트를 샘플링하여 수행한다.", "테스트결과서", "테스트 수행 샘플링 \n기준 (고객제시)", "QE", skills="V&V", remote=True)
a("2-3-12", "통합 테스트 시나리오 및 케이스 검토", "각 파트에서 가이드에 따라 작성한 통테 시나리오/케이스를 QE가 검토한 후 시정조치를 진행한다.", "검토결과서", "통테 시나리오/케이스 작성 가이드", "Other", guiding="QE", feedback="QE", skills="V&V")
a("2-3-13", "구축단계 요구사항 추적 내용 검토 및 확인", "구축단게말 요구사항 추적매트릭스 검토 및 확인을 수행한다.", "검토결과서", "요구사항추적표", "QE\nOther", feedback="QE", skills="V&V", repeat=True)
a("2-3-14", "구축단계말 검토(리뷰 Sampling)\n  - QA 승인\n  - 고객 승인", "구축단계 작성 및 보완된 산출물에 대해 단계말에 최종 검토를 수행하고 이를 보완하여 제출한다.", "검토결과서", "구축단계 산출물", "QE\nOther", feedback="QE", skills="V&V", reg="O", repeat=True, remote=True)
a("2-3-15", "구축단계말 산출물 Baseline 수립\n  - 형상감사 포함", "구축단계말 제출되고 고객 승인이 완료된 산출물에 대해 Baseline을 수립한다.\n  - 사전에 형상감사를 통해 구성항목의 정확성, 완전성, 무결성을 확인\n  - 다음단계 변경관리를 위한 기준선을 설정", "형상감사보고서 (Optional)", "구축단계 승인산출물", "QE", skills="CM", repeat=True)

# ---- 2-4 테스트 ----
a("2-4-1", "테스트 산출물 작성 가이드", "각 테스트 산출물에 대한 작성법을 정리하여 문서화한 후 해당 내용을 구성원에게 교육한다.", "테스트 산출물 작성 가이드 및 교육자료", "총괄테스트계획서\n통합테스트계획서", "QE", skills="SW공학 프로세스", remote=True)
a("2-4-2", "테스트 진척 관리\n - 통합 테스트 수행 진척 관리 및 보고", "통합테스트 수행 현황 전반에 대하여 진척관리를 수행한다. (모수, 진척, 결함, 이슈 등)", "통합테스트 진척관리 통계", "통합테스트계획서", "Other", guiding="QE", feedback="QE", skills="SW지표, 측정/분석")
a("2-4-3", "일괄도급이 포함된 경우, 도급 품질 점검 결과 관리 및 결과서 업체 송부", "도급영역 수행에서 수행한 품질점검 결과를 검토하고 결과를피드백 한다.", "점검 결과서", "도급영역 품질검토 결과서", "QE", skills="법/제도|전사규정", reg="O", repeat=True, remote=True)
a("2-4-4", "주단위 수집된 프로젝트 지표에 대한 분석 / 품질평가/ 시정조치", "주단위 지표를 수집하고 입력한다.", "주단위 지표 입력", "측정계획서", "QE\nOther", feedback="QE", skills="법/제도|전사규정|SW지표, 측정/분석", reg="O", meth="O", repeat=True)
a("2-4-5", "테스트단계 결함 및 시정조치 관리(결함 집계, 피드백 및 조치결과 확인)", "테스트 단계 시 발생되는 결함에 대하여 집계, 검토 후 피드백, 시정조치 결과 확인 업무를 수행한다.", "주간보고서 \n수시보고서", "결함등록 현황", "QE", skills="V&V", repeat=True)
a("2-4-6", "테스트단계 결함 발생 원인 분석, 재발 방지책 수립 및 이행", "테스트 단계 시 발생결함 중 주요 결함에 대한 원인 분석 및 재발 방지책을 수립하고 이행한다.", "결함보고서\n(원인분석/재발방지 측면)", "테스트단계 발생 결함", "QE\nOther", feedback="QE", skills="V&V", repeat=True)
a("2-4-7", "테스트단계말 품질지표 측정 (정성/정량)\n  - 범위 증감  확인, 생산성 등 필수지표", "테스트 단계말 정성/정량 품질지표를 측정한다.", "측정보고서", "변경요청서", "QE", skills="SW지표, 측정/분석", repeat=True)
a("2-4-8", "테스트단계 산출물 리뷰\n  - 표준준수\n  - 상세화 및 적합성 검토", "테스트단계 산출물 대상으로 리뷰를 수행한다. ", "검토결과서", "전개단계 산출물", "QE", skills="V&V", repeat=True, remote=True)
a("2-4-9", "테스트단계말 검토(리뷰 Sampling)\n  - QA 승인\n  - 고객 승인", "테스트단계 작성 및 보완된 산출물에 대해 단계말에 최종 검토를 수행하고 이를 보완하여 제출한다.", "검토결과서", "테스트단계 산출물", "QE\nOther", feedback="QE", skills="V&V", reg="O", repeat=True, remote=True)
a("2-4-10", "테스트단계말 산출물 Baseline 수립\n  - 형상감사 포함", "테스트단계말 제출되고 고객 승인이 완료된 산출물에 대해 Baseline을 수립한다.\n  - 사전에 형상감사를 통해 구성항목의 정확성, 완전성, 무결성을 확인\n  - 다음단계 변경관리를 위한 기준선을 설정", "형상감사보고서 (Optional)", "테스트단계 승인산출물", "QE", skills="CM", repeat=True)

# ---- 2-5 전개(이행) ----
a("2-5-1", "이행계획 수립\n  - 안정화 방안 포함", "이행 (사전이행/본이행/후이행) 의 각 항목별 일정/절차/방안에 대해 검토한다.", "이행계획서 ", "요구사항정의서 (이행관련 요구사항)", "Other", feedback="QE", skills="SW공학 프로세스")
a("2-5-2", "오픈 전략 지표 수립", "오픈 의사결정 시 활용되는 오픈전략지표에 대해 각 영역별로 적절히 구성되 있는지 검토한다. ", "오픈전략지표 \n(이행계획서 별첨자료)", "요구사항정의서 (오픈관련 요구사항)", "QE\nOther", feedback="QE", skills="SW지표, 측정/분석")
a("2-5-3", "인수인계 계획 수립", "프로젝트 투입 인원에 대한 인수인계 계획에 대해 검토를 수행한다.", "인수인계계획서", "요구사항정의서\n(인수인계 관련 요구사항)", "Other", feedback="QE", skills="SW지표, 측정/분석")
a("2-5-4", "일괄도급이 포함된 경우, 도급 품질 점검 결과 관리 및 결과서 업체 송부", "도급영역 수행에서 수행한 품질점검 결과를 검토하고 결과를피드백 한다.", "점검 결과서", "도급영역 품질검토 결과서", "QE", skills="법/제도|전사규정", reg="O", repeat=True, remote=True)
a("2-5-5", "주단위 수집된 프로젝트 지표에 대한 분석 / 품질평가/ 시정조치", "주단위 지표를 수집하고 입력한다.", "주단위 지표 입력", "측정계획서", "QE\nOther", feedback="QE", skills="법/제도|전사규정|SW지표, 측정/분석", reg="O", meth="O", repeat=True)
a("2-5-6", "전개단계 결함 및 시정조치 관리(결함 집계, 피드백 및 조치결과 확인)", "전개단계 시 발생되는 결함에 대하여 집계, 검토 후 피드백, 시정조치 결과 확인 업무를 수행한다.", "주간보고서 \n수시보고서", "결함등록 현황", "QE", skills="V&V", repeat=True)
a("2-5-7", "전개단계 결함 발생 원인 분석, 재발 방지책 수립 및 이행", "전개단계 시 발생결함 중 주요 결함에 대한 원인 분석 및 재발 방지책을 수립하고 이행한다.", "결함보고서\n(원인분석/재발방지 측면)", "전개단계 발생 결함", "QE\nOther", feedback="QE", skills="V&V", repeat=True)
a("2-5-8", "전개단계말 품질지표 측정 (정성/정량)\n  - 범위 증감  확인, 생산성 등 필수지표", "전개단계말 정성/정량 품질지표를 측정한다.", "측정보고서", "변경요청서", "QE\nOther", feedback="QE", skills="SW지표, 측정/분석", repeat=True)
a("2-5-9", "전개단계 산출물 리뷰\n  - 표준준수\n  - 상세화 및 적합성 검토", "전개단계 산출물 대상으로 리뷰를 수행한다. ", "검토결과서", "전개단계 산출물", "QE\nOther", feedback="QE", skills="V&V", repeat=True, remote=True)
a("2-5-10", "전개단계말 검토(리뷰 Sampling)\n  - QA 승인\n  - 고객 승인", "전개단계 작성 및 보완된 산출물에 대해 단계말에 최종 검토를 수행하고 이를 보완하여 제출한다.", "검토결과서", "전개단계 산출물", "QE\nOther", feedback="QE", skills="V&V", reg="O", repeat=True, remote=True)

# ---- 2-6 종료 ----
a("2-6-1", "오픈 후 결함 관리", "시스템 오픈 후 발생하는 결함을 대상으로 결함발생율, 결함조치율 등 지표를 관리한다. ", "결함관리대장\n(시스템 활용)", "오픈 완료 보고서", "QE", skills="SW지표, 측정/분석", remote=True)
a("2-6-2", "일괄도급이 포함된 경우, 도급 품질 점검 결과 관리 및 결과서 업체 송부", "도급영역 수행에서 수행한 품질점검 결과를 검토하고 결과를피드백 한다.", "점검 결과서", "도급영역 품질검토 결과서", "QE", skills="법/제도|전사규정", reg="O", repeat=True, remote=True)
a("2-6-3", "주단위 수집된 프로젝트 지표에 대한 분석 / 품질평가/ 시정조치", "주단위 지표를 수집하고 입력한다.", "주단위 지표 입력", "측정계획서", "QE\nOther", feedback="QE", skills="법/제도|전사규정|SW지표, 측정/분석", reg="O", meth="O", repeat=True)
a("2-6-4", "최종 산출물 점검 및 고객 제출", "고객 검수기준에 따른 최종산출물을 점검/확인 후 고객에게 제출한다.", "최종산출물 (검수목록 기준)", "검사/검수계획서", "QE", skills="CM", reg="O", meth="O", remote=True)

GLOSSARY = [
    ("g01", "RFP", "제안요청서(Request For Proposal). 고객이 프로젝트 발주를 위해 요구사항을 정리해 배포하는 문서."),
    ("g02", "WBS", "작업분류체계(Work Breakdown Structure). 프로젝트 작업을 세부 단위로 나눈 것으로, 일정관리의 기준이 되는 문서."),
    ("g03", "R&R", "역할과 책임(Role & Responsibility). 프로젝트 구성원·팀별로 누가 무엇을 담당하는지 정의한 것."),
    ("g04", "QE", "품질담당자(Quality Engineer). 프로젝트의 품질 활동을 관리·지원하는 품질팀 담당자."),
    ("g05", "QA", "품질보증(Quality Assurance). 프로세스가 표준·규정대로 지켜지는지 확인하는 활동."),
    ("g06", "CM", "형상관리(Configuration Management). 산출물·코드 등의 버전과 변경 이력을 관리하는 활동."),
    ("g07", "V&V", "검증 및 확인(Verification & Validation). 결과물이 요구사항에 맞고 올바르게 동작하는지 점검하는 활동."),
    ("g08", "Tailoring", "표준 방법론이나 프로세스를 프로젝트 특성에 맞게 조정하는 것."),
    ("g09", "Sign-off", "특정 산출물이나 결과에 대해 책임자가 최종 승인했음을 확인하는 절차."),
    ("g10", "감리 (Audit)", "외부 감리기관이 프로젝트 수행의 적절성을 점검하는 활동."),
    ("g11", "PMO", "프로젝트 관리 오피스(Project Management Office). 여러 프로젝트의 관리 표준·방법론을 지원하고 감독하는 조직."),
    ("g12", "Guiding", "품질팀 R&R 중 하나로, 개발팀에게 방법과 기준을 안내하는 역할."),
    ("g13", "Doing (수행)", "품질팀 R&R 중 하나로, 품질 활동을 품질팀이 직접 수행하는 역할."),
    ("g14", "Feed-Back", "품질팀 R&R 중 하나로, 수행 결과를 점검하고 개선사항을 전달하는 역할."),
    ("g15", "게이트 (Gate)", "다음 단계로 넘어가기 전에 반드시 충족해야 하는 통과 기준."),
    ("g16", "산출물 (Deliverable)", "특정 활동의 결과로 만들어지는 문서나 결과물."),
    ("g17", "착수", "계약 체결 이후 프로젝트 수행을 실제로 시작하는 초기 단계."),
    ("g18", "전개 (이행)", "구축이 끝난 시스템을 실제 운영 환경에 적용·이전하는 단계."),
]


def main() -> None:
    if DB_PATH.exists():
        if "--force" not in sys.argv:
            sys.exit(f"{DB_PATH.name} 이(가) 이미 있습니다. 덮어쓰려면 --force 를 붙이세요 (체크 진행 상황도 함께 삭제됩니다).")
        DB_PATH.unlink()

    dump = lambda v: json.dumps(v, ensure_ascii=False)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO project_types VALUES (?,?,?)", PROJECT_TYPES)
        conn.executemany('INSERT INTO phases (id, project_type_id, "group", name, "order") VALUES (?,?,?,?,?)', PHASES)
        conn.executemany(
            "INSERT INTO activities (id, phase_id, title, description, repeat_per_phase, remote_support_possible, "
            "deliverable_json, quality_role_json, required_skills_json, standard_ref_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (x["id"], x["phase_id"], x["title"], x["description"], int(x["repeat_per_phase"]),
                 int(x["remote_support_possible"]), dump(x["deliverable"]), dump(x["quality_role"]),
                 dump(x["required_skills"]) if x["required_skills"] else None, dump(x["standard_ref"]))
                for x in ACTS
            ],
        )
        conn.executemany("INSERT INTO glossary VALUES (?,?,?)", GLOSSARY)
        conn.commit()
    finally:
        conn.close()
    print(f"생성 완료: {DB_PATH.name} (활동 {len(ACTS)}개, 용어 {len(GLOSSARY)}개)")


if __name__ == "__main__":
    main()
