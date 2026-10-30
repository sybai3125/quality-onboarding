"""
품질 온보딩 네비게이터 - 데이터 로더 (SQLite 버전)

quality_onboarding_navigator.db (SQLite 파일)를 읽어서
1) 유형 선택 -> 2) 단계 선택 -> 3) 가이드 조회 -> 4) 셀프 체크 -> 5) 용어사전
에 필요한 조회 함수를 제공한다. (glossary도 이 DB 안에 같은 파일로 들어있다.)

예전에는 quality_onboarding_navigator_data.json 파일을 통째로 읽고 썼는데,
DBeaver 같은 DB 툴로 데이터를 직접 보고 관리할 수 있게 SQLite로 옮겼다.
DB 파일 하나(quality_onboarding_navigator.db)에 아래 테이블들이 들어있다.

  - project_types / phases / activities / glossary : 품질 활동 가이드 데이터
  - progress_checked / progress_due_dates / progress_notes : 셀프체크 진행 상황
    (체크 여부, 마감일, 코멘트) - 예전엔 별도 progress json 파일이었다.

이 파일을 처음 쓰는 사람은 아래에서 만든 quality_onboarding_navigator.db를
DBeaver에서 "새 연결 -> SQLite -> 파일 선택"으로 열어보면 테이블을 그대로
조회/수정할 수 있다.

호출하는 쪽(UI_test.py)에서 보면 달라지는 게 거의 없다 - load_data()가
돌려주는 dict 모양, get_*/search_*/add_*/update_*/delete_* 함수들의 입력과
출력은 예전 JSON 버전과 100% 동일하다. 안에서 파일을 읽는 방식(JSON -> SQLite)만
바뀌었다.
"""

import json                       # 활동의 중첩 구조(deliverable, quality_role 등)를
                                    # DB 컬럼 안에 텍스트로 저장/복원하기 위해 사용
import sqlite3                    # SQLite DB 파일을 읽고 쓰기 위한 표준 라이브러리
from pathlib import Path          # 운영체제(윈도우/맥/리눅스)에 상관없이 파일 경로를 다루기 위한 표준 라이브러리
from functools import lru_cache   # 함수 결과를 메모리에 캐싱해서, 같은 인자로 다시 호출하면 재실행 없이 캐시값을 돌려주는 데코레이터

# 이 파일과 같은 폴더에 quality_onboarding_navigator.db 를 둔다고 가정.
# __file__ = 현재 이 loader.py 파일의 경로, .parent = 그 파일이 들어있는 폴더
DB_PATH = Path(__file__).parent / "quality_onboarding_navigator.db"


class DataValidationError(Exception):
    # 데이터 검증(_validate)에 실패했을 때 발생시킬 전용 예외.
    # 그냥 Exception을 써도 되지만, 이름을 따로 두면 "이건 데이터 문제다"라고 바로 알아볼 수 있다.
    pass


def _validate(data: dict) -> None:
    """필수 키와 참조 무결성(activity.phase_id -> phase.id)을 점검한다."""
    required_keys = {"project_types", "phases", "activities"}
    # JSON 최상위에 반드시 있어야 할 3개 키를 집합(set)으로 정의

    missing = required_keys - data.keys()
    # required_keys 중에서 실제 data에 없는 키만 남긴다 (집합 차집합 연산)

    if missing:
        # missing 집합이 비어있지 않다면 = 필수 키가 하나라도 빠졌다는 뜻
        raise DataValidationError(f"필수 최상위 키 누락: {missing}")
        # 어떤 키가 빠졌는지 메시지에 담아 예외를 던지고 즉시 함수 종료

    type_ids = {t["id"] for t in data["project_types"]}
    # project_types 배열에 있는 모든 유형의 id만 모아 집합으로 만든다 (예: {"new"})

    for p in data["phases"]:
        # phases 배열을 하나씩 순회
        if p["project_type_id"] not in type_ids:
            # 이 단계(phase)가 참조하는 project_type_id가 실제 유형 목록에 없다면 = 잘못된 참조
            raise DataValidationError(
                f"phase '{p['id']}'의 project_type_id '{p['project_type_id']}'가 "
                f"project_types에 존재하지 않음"
            )
            # 어떤 phase가 문제인지 id를 포함해 예외를 던진다

    phase_ids = {p["id"] for p in data["phases"]}
    # phases 배열에 있는 모든 단계의 id만 모아 집합으로 만든다 (예: {"1-1", "1-2", ...})

    for a in data["activities"]:
        # activities 배열을 하나씩 순회
        if a["phase_id"] not in phase_ids:
            # 이 활동(activity)이 참조하는 phase_id가 실제 단계 목록에 없다면 = 잘못된 참조
            raise DataValidationError(
                f"activity '{a['id']}'의 phase_id '{a['phase_id']}'가 phases에 존재하지 않음"
            )
            # 어떤 activity가 문제인지 id를 포함해 예외를 던진다


# ---------------------------------------------------------------------------
# SQLite 스키마
# activity의 deliverable/quality_role/required_skills/standard_ref는 원래
# JSON에서도 중첩 구조(dict/list)였다. 이걸 테이블 여러 개로 잘게 쪼개면
# 조회 함수(get_activity 등)가 훨씬 복잡해지므로, 그 부분만 JSON 텍스트로
# 컬럼에 그대로 저장하고(예: deliverable_json), 읽어올 때 다시 dict/list로
# 풀어준다. DBeaver로 열어도 그 컬럼 값이 JSON 문자열로 보일 뿐, 나머지
# 컬럼(제목/설명/단계 등)은 평범한 텍스트/숫자 컬럼이라 그대로 보고 고칠 수 있다.
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_types (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS phases (
    id TEXT PRIMARY KEY,
    project_type_id TEXT NOT NULL REFERENCES project_types(id),
    "group" TEXT,
    name TEXT NOT NULL,
    "order" INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY,
    phase_id TEXT NOT NULL REFERENCES phases(id),
    title TEXT NOT NULL,
    description TEXT,
    repeat_per_phase INTEGER NOT NULL DEFAULT 0,
    remote_support_possible INTEGER NOT NULL DEFAULT 0,
    deliverable_json TEXT,
    quality_role_json TEXT,
    required_skills_json TEXT,
    standard_ref_json TEXT
);

CREATE TABLE IF NOT EXISTS glossary (
    id TEXT PRIMARY KEY,
    term TEXT NOT NULL,
    definition TEXT
);

-- ---- 셀프체크 진행 상황 (예전 progress json 대체) ----
CREATE TABLE IF NOT EXISTS progress_checked (
    activity_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS progress_due_dates (
    activity_id TEXT PRIMARY KEY,
    due_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progress_notes (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL
);
"""


def _connect(path: str | None = None) -> sqlite3.Connection:
    """DB 파일에 연결하고, 테이블이 아직 없으면(첫 실행) 스키마를 만든다.
    row_factory를 sqlite3.Row로 해두면 컬럼 이름으로 값을 꺼낼 수 있다
    (r["title"]처럼) - 튜플 인덱스(r[2])로 접근하는 것보다 훨씬 안전하다."""
    p = Path(path) if path else DB_PATH
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


@lru_cache(maxsize=1)
# 이 함수를 캐싱한다: 인자가 같으면(대부분 인자 없이 호출) 두 번째 호출부터는
# DB를 다시 읽지 않고 첫 호출 때 만든 결과를 그대로 돌려준다.
def load_data(path: str | None = None) -> dict:
    """
    SQLite DB를 읽어 예전 JSON 버전과 똑같은 모양의 dict로 반환한다.
    (project_types/phases/activities/glossary 키를 가진 dict - 호출하는 쪽은
    데이터가 JSON에서 왔는지 DB에서 왔는지 신경 쓸 필요가 없다.)
    lru_cache로 감싸져 있어 앱 실행 중에는 DB를 한 번만 읽는다.
    """
    conn = _connect(path)
    try:
        project_types = [
            {"id": r["id"], "name": r["name"], "description": r["description"]}
            for r in conn.execute("SELECT id, name, description FROM project_types")
        ]

        phases = [
            {
                "id": r["id"],
                "project_type_id": r["project_type_id"],
                "group": r["group"],
                "name": r["name"],
                "order": r["order"],
            }
            for r in conn.execute(
                'SELECT id, project_type_id, "group", name, "order" FROM phases'
            )
        ]

        activities = []
        for r in conn.execute(
            "SELECT id, phase_id, title, description, repeat_per_phase, "
            "remote_support_possible, deliverable_json, quality_role_json, "
            "required_skills_json, standard_ref_json FROM activities"
        ):
            activities.append(
                {
                    "id": r["id"],
                    "phase_id": r["phase_id"],
                    "title": r["title"],
                    "description": r["description"],
                    "repeat_per_phase": bool(r["repeat_per_phase"]),
                    "remote_support_possible": bool(r["remote_support_possible"]),
                    "deliverable": json.loads(r["deliverable_json"]) if r["deliverable_json"] else None,
                    "quality_role": json.loads(r["quality_role_json"]) if r["quality_role_json"] else None,
                    "required_skills": json.loads(r["required_skills_json"]) if r["required_skills_json"] else [],
                    "standard_ref": json.loads(r["standard_ref_json"]) if r["standard_ref_json"] else None,
                }
            )

        glossary = [
            {"id": r["id"], "term": r["term"], "definition": r["definition"]}
            for r in conn.execute("SELECT id, term, definition FROM glossary")
        ]
    finally:
        conn.close()

    data = {
        "project_types": project_types,
        "phases": phases,
        "activities": activities,
        "glossary": glossary,
    }
    _validate(data)
    # 위에서 만든 검증 함수를 호출해서, 구조가 깨져 있으면 여기서 바로 예외가 발생하고 멈춘다

    return data


def get_project_types(data: dict) -> list[dict]:
    """1. 유형 선택 화면에서 쓸 유형 목록."""
    return data["project_types"]
    # 가공 없이 project_types 배열을 그대로 반환 (신규/고도화·전환/SM/AI적용 목록)


def get_phases(data: dict, project_type_id: str) -> list[dict]:
    """2. 단계 선택 화면에서 쓸, 특정 유형에 속한 단계 목록 (order 기준 정렬)."""
    phases = [p for p in data["phases"] if p["project_type_id"] == project_type_id]
    # phases 전체 중에서, 사용자가 1단계에서 고른 유형(project_type_id)과 일치하는 것만 골라낸다

    return sorted(phases, key=lambda p: p["order"])
    # 걸러낸 단계들을 order 필드(화면 표시 순서) 기준으로 오름차순 정렬해서 반환


def get_activities(data: dict, phase_id: str) -> list[dict]:
    """3. 가이드 조회 화면에서 쓸, 특정 단계에 속한 활동 목록."""
    return [a for a in data["activities"] if a["phase_id"] == phase_id]
    # activities 전체 중에서, 사용자가 2단계에서 고른 단계(phase_id)에 속한 활동만 골라 반환


def get_activity(data: dict, activity_id: str) -> dict | None:
    """활동 id로 단건 조회 (셀프체크 화면에서 활동 상세를 다시 보여줄 때 등)."""
    return next((a for a in data["activities"] if a["id"] == activity_id), None)
    # activities를 순회하며 id가 일치하는 첫 번째 항목을 반환


def get_all_activities(data: dict, project_type_id: str) -> list[dict]:
    """4. 셀프 체크 전체 진행률 계산용 - 특정 유형에 속한 모든 단계의 활동을 다 합쳐서 반환."""
    result: list[dict] = []
    for phase in get_phases(data, project_type_id):
        # 유형에 속한 단계를 순서대로 돌면서, 각 단계의 활동 목록을 이어붙인다
        result.extend(get_activities(data, phase["id"]))
    return result


def search_activities(data: dict, project_type_id: str, keyword: str) -> list[dict]:
    """3. 가이드 조회 검색용 - 선택한 유형 전체(모든 단계)에서 제목/설명에 keyword가
    포함된 활동만 대소문자 구분 없이 검색. keyword가 비어있으면 빈 리스트를 반환한다
    (검색어가 없을 땐 기존처럼 '단계 선택' 기반 목록을 보여주면 되기 때문)."""
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return []

    matches = []
    for a in get_all_activities(data, project_type_id):
        title = a.get("title") or ""
        desc = a.get("description") or ""
        if keyword in title.lower() or keyword in desc.lower():
            matches.append(a)
    return matches
 

def get_glossary(data: dict) -> list[dict]:
    """5. 용어사전 화면에서 쓸 전체 용어 목록. glossary 키가 없는 구버전 데이터도 에러 없이 빈 리스트를 반환."""
    return data.get("glossary", [])
    # dict.get(key, 기본값)은 key가 없어도 KeyError 없이 기본값(여기선 빈 리스트)을 돌려준다


def search_glossary(data: dict, keyword: str) -> list[dict]:
    """용어명 또는 설명에 keyword가 포함된 용어만 대소문자 구분 없이 검색."""
    keyword = (keyword or "").strip().lower()
    # 검색어 앞뒤 공백을 지우고 소문자로 바꿔서, 대소문자/공백 차이로 못 찾는 일을 막는다

    if not keyword:
        # 검색어가 비어있으면(입력 전) 전체 목록을 그대로 반환
        return get_glossary(data)

    return [
        g for g in get_glossary(data)
        if keyword in g["term"].lower() or keyword in g["definition"].lower()
    ]
    # 각 용어의 term(용어명)이나 definition(설명) 안에 검색어가 포함되어 있으면 결과에 포함


# ---------------------------------------------------------------------------
# 용어사전 CRUD (Create / Update / Delete)
# 아래 세 함수는 메모리 안의 data만 바꾼다. 실제 DB에 반영하려면
# 반드시 save_data(data)를 별도로 호출해야 한다. (조회 함수들과 마찬가지로
# data를 직접 손대는 대신, 호출한 쪽이 "언제 저장할지"를 결정하게 하기 위함)
# ---------------------------------------------------------------------------

def _next_glossary_id(glossary: list[dict]) -> str:
    """기존 용어 id(g01, g02, ...) 중 가장 큰 번호 다음 번호를 만들어낸다."""
    max_num = 0
    for g in glossary:
        gid = g.get("id", "")
        if gid.startswith("g") and gid[1:].isdigit():
            max_num = max(max_num, int(gid[1:]))
    return f"g{max_num + 1:02d}"
    # :02d는 숫자를 최소 2자리로, 부족하면 앞에 0을 채워서 표시 (예: 3 -> "03")


def add_glossary_term(data: dict, term: str, definition: str) -> dict:
    """Create - 용어사전에 새 용어를 추가하고, 새로 만들어진 항목을 반환한다."""
    glossary = data.setdefault("glossary", [])
    # setdefault: "glossary" 키가 이미 있으면 그 값을 쓰고, 없으면 빈 리스트를
    # 새로 만들어 넣어준다 (구버전 데이터에 glossary가 없어도 에러 없이 동작)

    new_entry = {
        "id": _next_glossary_id(glossary),
        "term": term,
        "definition": definition,
    }
    glossary.append(new_entry)
    return new_entry


def update_glossary_term(
    data: dict, term_id: str, term: str | None = None, definition: str | None = None
) -> bool:
    """Update - id로 용어를 찾아 term/definition을 갱신한다.
    term 또는 definition에 None을 넘기면 그 필드는 건드리지 않는다.
    찾아서 수정했으면 True, 그런 id가 없으면 False를 반환한다."""
    for g in get_glossary(data):
        if g["id"] == term_id:
            if term is not None:
                g["term"] = term
            if definition is not None:
                g["definition"] = definition
            return True
    return False


def delete_glossary_term(data: dict, term_id: str) -> bool:
    """Delete - id로 용어를 찾아 목록에서 제거한다.
    찾아서 지웠으면 True, 그런 id가 없으면 False를 반환한다."""
    glossary = data.get("glossary", [])
    for i, g in enumerate(glossary):
        if g["id"] == term_id:
            del glossary[i]
            return True
    return False


# ---------------------------------------------------------------------------
# 활동(activity) CRUD (Update / Delete)
# 프로젝트마다 94개 활동 중 일부는 "이번 프로젝트엔 안 맞음" 같은 이유로
# 내용을 바꾸거나 아예 빼야 할 수 있다. id(예: "1-1-7")는 그대로 두고
# title/description 같은 내용만 바꾸는 update, 통째로 빼는 delete를 제공한다.
# 글로서리 CRUD와 마찬가지로 메모리 안의 data만 바꾸고, DB에 반영하려면
# save_data(data)를 별도로 호출해야 한다.
# ---------------------------------------------------------------------------

def update_activity(
    data: dict,
    activity_id: str,
    title: str | None = None,
    description: str | None = None,
) -> bool:
    """Update - id로 활동을 찾아 title/description을 갱신한다.
    title 또는 description에 None을 넘기면 그 필드는 건드리지 않는다.
    찾아서 수정했으면 True, 그런 id가 없으면 False를 반환한다."""
    act = get_activity(data, activity_id)
    if act is None:
        return False
    if title is not None:
        act["title"] = title
    if description is not None:
        act["description"] = description
    return True


def delete_activity(data: dict, activity_id: str) -> bool:
    """Delete - id로 활동을 찾아 목록에서 제거한다.
    찾아서 지웠으면 True, 그런 id가 없으면 False를 반환한다."""
    activities = data.get("activities", [])
    for i, a in enumerate(activities):
        if a["id"] == activity_id:
            del activities[i]
            return True
    return False


def save_data(data: dict, path: str | None = None) -> None:
    """메모리에 있는 data를 SQLite DB에 다시 저장한다 (활동 CRUD를 붙일 때도
    이 함수를 그대로 재사용할 수 있다). 저장하기 전에 _validate로 한 번 더
    구조를 검증해서, 실수로 깨진 데이터가 DB에 그대로 저장되는 걸 막는다.

    "그때그때 UPDATE"가 아니라, 4개 테이블을 통째로 비우고 data의 내용으로
    다시 채우는 방식이다(예전 JSON 버전이 파일을 통째로 덮어쓰던 것과 같은
    방식). 데이터 양이 적어서(활동 94개 수준) 성능 문제는 없고, 추가/수정/
    삭제 로직을 데이터 종류별로 따로 짜지 않아도 되는 장점이 있다."""
    _validate(data)

    conn = _connect(path)
    try:
        conn.execute("DELETE FROM activities")
        conn.execute("DELETE FROM phases")
        conn.execute("DELETE FROM project_types")
        conn.execute("DELETE FROM glossary")

        conn.executemany(
            "INSERT INTO project_types (id, name, description) VALUES (?, ?, ?)",
            [(t["id"], t["name"], t.get("description")) for t in data["project_types"]],
        )
        conn.executemany(
            'INSERT INTO phases (id, project_type_id, "group", name, "order") VALUES (?, ?, ?, ?, ?)',
            [
                (p["id"], p["project_type_id"], p.get("group"), p["name"], p["order"])
                for p in data["phases"]
            ],
        )
        conn.executemany(
            "INSERT INTO activities (id, phase_id, title, description, repeat_per_phase, "
            "remote_support_possible, deliverable_json, quality_role_json, "
            "required_skills_json, standard_ref_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    a["id"],
                    a["phase_id"],
                    a["title"],
                    a.get("description"),
                    int(bool(a.get("repeat_per_phase"))),
                    int(bool(a.get("remote_support_possible"))),
                    json.dumps(a["deliverable"], ensure_ascii=False) if a.get("deliverable") is not None else None,
                    json.dumps(a["quality_role"], ensure_ascii=False) if a.get("quality_role") is not None else None,
                    json.dumps(a["required_skills"], ensure_ascii=False) if a.get("required_skills") else None,
                    json.dumps(a["standard_ref"], ensure_ascii=False) if a.get("standard_ref") is not None else None,
                )
                for a in data["activities"]
            ],
        )
        conn.executemany(
            "INSERT INTO glossary (id, term, definition) VALUES (?, ?, ?)",
            [(g["id"], g["term"], g.get("definition")) for g in data.get("glossary", [])],
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 셀프체크 진행 상황 저장/불러오기 (UserProgress)
# quality_onboarding_navigator.db의 project_types/phases/activities/glossary는
# "품질 활동이 뭔지"를 담는 공용 데이터라서 사람마다 다른 체크 상태·코멘트를
# 여기에 같이 섞어 넣으면 안 된다. 그래서 진행 상황은 같은 DB 파일 안이지만
# 별도 테이블(progress_checked / progress_due_dates / progress_notes)에 담는다.
# load_progress()가 돌려주는 dict 모양은 예전 progress json 파일과 동일하다:
#   {
#     "checked_activities": ["1-1-1", "1-1-3", ...],
#     "activity_notes": {"1-1-1": [{"id": "...", "text": "...", "status": "진행 중"}, ...]},
#     "due_dates": {"1-1-1": "2026-09-30", ...}
#   }
# ---------------------------------------------------------------------------

def load_progress(path: str | None = None) -> dict:
    """진행 상황 테이블들을 읽어온다. DB가 방금 새로 만들어졌으면(맨 처음
    실행) 테이블은 있지만 비어있으므로 빈 상태를 그대로 돌려준다 - 예전
    JSON 버전에서 "파일이 없으면 빈 상태"였던 것과 동작이 같다."""
    conn = _connect(path)
    try:
        checked_activities = [
            r["activity_id"] for r in conn.execute("SELECT activity_id FROM progress_checked")
        ]
        due_dates = {
            r["activity_id"]: r["due_date"]
            for r in conn.execute("SELECT activity_id, due_date FROM progress_due_dates")
        }
        activity_notes: dict[str, list[dict]] = {}
        for r in conn.execute("SELECT id, activity_id, text, status FROM progress_notes"):
            activity_notes.setdefault(r["activity_id"], []).append(
                {"id": r["id"], "text": r["text"], "status": r["status"]}
            )
    finally:
        conn.close()

    return {
        "checked_activities": checked_activities,
        "activity_notes": activity_notes,
        "due_dates": due_dates,
    }


def save_progress(progress: dict, path: str | None = None) -> None:
    """진행 상황을 진행 상황 테이블들에 통째로 다시 써서 저장한다. save_data와
    똑같이 "비우고 다시 채우는" 방식이지만, _validate는 하지 않는다(활동
    데이터 스키마와 무관한 별도 테이블들이라 검증할 필요가 없다)."""
    conn = _connect(path)
    try:
        conn.execute("DELETE FROM progress_checked")
        conn.execute("DELETE FROM progress_due_dates")
        conn.execute("DELETE FROM progress_notes")

        conn.executemany(
            "INSERT INTO progress_checked (activity_id) VALUES (?)",
            [(act_id,) for act_id in progress.get("checked_activities", [])],
        )
        conn.executemany(
            "INSERT INTO progress_due_dates (activity_id, due_date) VALUES (?, ?)",
            [
                (act_id, due)
                for act_id, due in progress.get("due_dates", {}).items()
                if due
            ],
        )
        note_rows = [
            (note["id"], act_id, note["text"], note["status"])
            for act_id, note_list in progress.get("activity_notes", {}).items()
            for note in note_list
        ]
        conn.executemany(
            "INSERT INTO progress_notes (id, activity_id, text, status) VALUES (?, ?, ?, ?)",
            note_rows,
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    # 이 파일을 "python loader.py"처럼 직접 실행했을 때만 아래 코드가 동작한다.
    # 다른 파일에서 import loader 로 불러올 때는 이 블록이 실행되지 않는다.

    data = load_data()
    # 기본 경로(DB_PATH)에서 데이터를 읽어온다

    print("유형:", [t["name"] for t in get_project_types(data)])
    # 유형 목록에서 이름만 뽑아 리스트로 출력 (예: ['신규'])

    phases = get_phases(data, "new")
    # 유형 id "new"(신규)에 속한 단계 목록을 가져온다

    print("단계:", [p["name"] for p in phases])
    # 단계 목록에서 이름만 뽑아 출력 (예: ['제안', '분석', ...])

    if phases:
        # 단계가 하나라도 있으면(리스트가 비어있지 않으면)

        acts = get_activities(data, phases[0]["id"])
        # 정렬된 단계 목록의 첫 번째 단계(order=1, 예: '제안')에 속한 활동들을 가져온다

        print(f"'{phases[0]['name']}' 단계 활동 수:", len(acts))
        # 그 단계에 활동이 몇 개 있는지 출력

        print("예시 활동:", acts[0]["title"] if acts else None)
        # 활동이 하나라도 있으면 첫 번째 활동의 제목(title)을 출력, 없으면 None 출력

    print("용어사전 개수:", len(get_glossary(data)))
    print("RFP 검색:", [g["term"] for g in search_glossary(data, "rfp")])