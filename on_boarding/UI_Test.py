"""
품질 온보딩 네비게이터 - UI (Streamlit)

1) 유형 선택 -> 2) 단계 선택 -> 3) 가이드 조회 -> 4) 셀프 체크 -> 5) 용어사전 화면을 구현한다.

데이터(유형/단계/활동/용어사전)와 셀프체크 진행 상황(체크 여부·코멘트·마감일)은
모두 loader.py를 통해 SQLite DB 파일(quality_onboarding_navigator.db) 하나에서
읽고 쓴다. 예전엔 JSON 파일 2개(데이터/진행상황)로 나눠서 관리했는데, DBeaver 같은
DB 툴로 직접 열어서 보거나 고칠 수 있게 SQLite로 옮겼다. session_state는 그
DB 값을 화면에 보여주는 동안만 잠깐 들고 있는 캐시일 뿐이고, 스크립트가 실행될
때마다(맨 아래 _persist_progress) DB에 다시 저장된다 - 브라우저를 새로고침해도
체크 상태는 사라지지 않는다.

실행 방법: streamlit run UI_test.py
loader.py가 같은 폴더에 있어야 하고, 그 옆에 quality_onboarding_navigator.db
파일이 함께 있어야 한다(loader.py의 DB_PATH가 그 파일을 가리킨다).
"""

import uuid
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st
from loader import (
    load_data,
    get_project_types,
    get_phases,
    get_activities,
    get_all_activities,
    search_activities,
    search_glossary,
    add_glossary_term,
    update_glossary_term,
    delete_glossary_term,
    update_activity,
    delete_activity,
    save_data,
    load_progress,
    save_progress,
    DataValidationError,
)

#----페이지 기본 설정 -------------
st.set_page_config(
    page_title = "품질 온보딩 네비게이터",
    layout ="wide",
)

# ---- Airbnb 스타일 테마 (getdesign.md의 airbnb DESIGN.md 참고) ---------
# 실제 에어비앤비 사이트를 그대로 베끼는 게 아니라, 이 앱(정보 밀도가 높은
# 내부 도구)에 맞게 색상·타이포그래피·버튼 모양만 가져와 적용한 것이다.
#   - 단일 액센트: Rausch #ff385c (버튼, 진행률 바) - 애플 테마의
#     Action Blue(#0066cc)를 대체
#   - 배경: 순백 캔버스(#ffffff) - 에어비앤비는 다크모드가 없다
#   - 사이드바도 굳이 어둡게 만들지 않고 밝은 회색(surface-soft, #f7f7f7)만
#     써서, 이전에 애플 테마에서 겪었던 "어두운 배경 위 흰 글자가 흰 위젯과
#     겹쳐 안 보이는" 버그 자체가 생길 여지를 없앴다.
#   - 타이포그래피: Airbnb Cereal이 없는 환경이라 Inter로 대체
#     (getdesign.md의 "Font Substitutes" 권장 사항)
#   - 버튼: 8px 라운드(에어비앤비는 완전한 pill이 아니라 살짝 둥근 모서리),
#     카드(expander): 14px 라운드 + 옅은 테두리 + 에어비앤비의 유일한
#     그림자 단계(호버 카드용)를 적용
def _inject_airbnb_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', Circular, -apple-system, system-ui, Roboto, sans-serif;
        }

        .stApp {
            background-color: #ffffff;
        }

        h1, h2, h3 {
            font-weight: 600;
            color: #222222;
        }

        section[data-testid="stSidebar"] {
            background-color: #f7f7f7;
            border-right: 1px solid #dddddd;
        }

        .stButton > button, .stFormSubmitButton > button {
            background-color: #ff385c;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 0.75rem 1.5rem;
            font-weight: 500;
            transition: background-color 0.15s ease;
        }
        .stButton > button:hover, .stFormSubmitButton > button:hover {
            background-color: #e00b41;
            color: #ffffff;
        }
        .stButton > button:active, .stFormSubmitButton > button:active {
            background-color: #e00b41;
        }

        div[data-testid="stExpander"] {
            background-color: #ffffff;
            border: 1px solid #dddddd;
            border-radius: 14px;
            box-shadow: rgba(0, 0, 0, 0.02) 0 0 0 1px, rgba(0, 0, 0, 0.04) 0 2px 6px 0,
                rgba(0, 0, 0, 0.1) 0 4px 8px 0;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
            border-radius: 8px;
            border: 1px solid #dddddd;
        }
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {
            border: 2px solid #222222;
            box-shadow: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

_inject_airbnb_theme()

# ---- 헬퍼: 진행률 막대를 직접 HTML로 그린다 ---------------------------
# st.progress()는 Streamlit/브라우저 버전에 따라 내부 DOM 구조(트랙과
# 채움 막대를 어떤 div로 나누는지)가 달라서, CSS로 "채움만 색칠"을
# 맞추려다 몇 번 실패했다(0%인데도 막대 전체가 채워진 것처럼 보이는 문제).
# 그래서 진행률 막대를 Streamlit 컴포넌트 대신 직접 만든 HTML/CSS로
# 그린다 - 구조를 내가 직접 정하니 항상 정확한 비율만큼만 채워진다.
def _progress_bar_html(ratio: float, height: int = 10) -> str:
    pct = max(0.0, min(1.0, ratio)) * 100
    return (
        f'<div style="background:#f2f2f2;border-radius:8px;'
        f'height:{height}px;width:100%;overflow:hidden;">'
        f'<div style="background:#ff385c;height:100%;width:{pct:.0f}%;'
        f'border-radius:8px;"></div></div>'
    )

# 용어사전 "관리자 모드"를 여는 코드. 이건 진짜 보안이 아니라, 신규 입사자가
# 실수로 용어사전을 고치는 걸 막기 위한 최소한의 장치일 뿐이다. 코드 안에
# 그대로 적혀있어서 누구나 파일만 열어보면 알 수 있으니, 민감한 정보를
# 지키는 용도로는 절대 쓰면 안 된다.
ADMIN_CODE = "qe2026"

#----data loading ---------------
# load_data()는 loader.py에서 @lru_cache가 걸려 있어 앱이 재실행돼도
# 파일을 매번 다시 읽지 않는다. 여기서는 데이터 파일이 없거나 구조가
# 깨졌을 때 사용자에게 원인을 바로 보여주기 위해 try/except로 감싼다.
try:
    data = load_data()
except FileNotFoundError:
    st.error(
        "Can't find Data File. Please check the path of loader.py DATA_PATH"
        "quality_onboarding_navigator_data.json 파일 위치를 확인해주세요"
    )
    st.stop()
except DataValidationError as e:
    st.error(f"데이터 파일 형식이 올바르지 않습니다: {e}")
    st.stop()

# ---- 셀프체크 진행 상황 불러오기 (세션당 한 번만) ----------------------
# Streamlit의 session_state는 "같은 브라우저 탭을 계속 쓰는 동안"만 살아있고,
# 새로고침하거나 앱을 껐다 켜면 초기화된다. 그래서 매 세션이 시작될 때
# (이 세션에서 아직 한 번도 불러온 적이 없을 때) 파일에 저장된 이전 진행
# 상황을 읽어와서 session_state에 미리 채워 넣는다. 이후로는 화면에서
# 체크박스/코멘트를 바꿀 때마다 session_state가 갱신되고, 스크립트 맨
# 아래(_persist_progress)에서 그 최신 상태를 다시 파일에 저장한다.
#
# 중요: 체크 상태/마감일은 st.checkbox·st.date_input 위젯 "자신의" key
# (check_활동id, due_활동id)에 그대로 의존하지 않는다. 다른 단계로 넘어가면
# 그 활동의 체크박스가 이번 실행에서는 아예 그려지지 않는데, Streamlit은
# 화면에 그려지지 않은 위젯의 값을 다음 실행에서 그대로 복원해주지 않을 때가
# 있다 - 그래서 "다른 단계를 눌렀다가 돌아오면 체크가 풀려있는" 버그가
# 생겼었다. 그래서 위젯이 그려지든 안 그려지든 항상 안전하게 남아있는
# 별도의 session_state(checked_activity_ids 집합, activity_due_dates 사전)를
# "진짜 저장소"로 두고, 체크박스/날짜 위젯은 그 저장소의 값을 보여주고
# 되돌려받는 용도로만 쓴다.
if "_progress_loaded" not in st.session_state:
    _saved_progress = load_progress()

    st.session_state["checked_activity_ids"] = set(_saved_progress.get("checked_activities", []))

    for _act_id, _act_notes in _saved_progress.get("activity_notes", {}).items():
        st.session_state[f"notes_{_act_id}"] = _act_notes

    st.session_state["activity_due_dates"] = {
        _act_id: date.fromisoformat(_due_str)
        for _act_id, _due_str in _saved_progress.get("due_dates", {}).items()
        if _due_str
    }

    st.session_state["_progress_loaded"] = True


def _persist_progress() -> None:
    """지금 이 세션에 있는 체크 상태/코멘트/마감일을 진행 상황 파일에
    통째로 다시 저장한다. 위젯을 하나 바꾸면 Streamlit이 스크립트를 처음부터
    다시 실행하는데(rerun), 이 함수를 스크립트 맨 끝에서 매번 호출해두면
    그 최신 상태가 항상 파일에 반영된다. checked_activity_ids/
    activity_due_dates에서 직접 읽어오기 때문에, 지금 화면에 어떤 단계가
    떠 있는지와 상관없이 모든 단계의 기록이 함께 저장된다."""
    checked_activities = sorted(st.session_state.get("checked_activity_ids", set()))
    activity_notes = {
        key[len("notes_"):]: value
        for key, value in st.session_state.items()
        if key.startswith("notes_") and value
    }
    due_dates = {
        act_id: due.isoformat()
        for act_id, due in st.session_state.get("activity_due_dates", {}).items()
        if due is not None
    }
    save_progress(
        {
            "checked_activities": checked_activities,
            "activity_notes": activity_notes,
            "due_dates": due_dates,
        }
    )


# ---- 헬퍼: 제목처럼 한 줄로 보여줄 텍스트를 안전하게 다듬는다 -----------
# 원본 엑셀의 title에는 두 가지 문제가 섞여 있다.
#   1) 줄바꿈(\n) - 예: 1-1-7 "범위,공정,자원에 따른 일정 수립\n - Task간의 ..."
#   2) 밑줄(_) - 예: 1-2-1 "...사전 준비_제안서 기반 품질전략 수립"
# 줄바꿈은 마크다운에서 새 문단/목록으로 해석되고, 밑줄(_)은 마크다운에서
# *기울임* 문법으로 해석된다. 그래서 title을 그냥 **굵게** 감싸서 한 줄
# 라벨로 쓰면, 줄바꿈 때문에 별표(**)가 깨지거나 밑줄 때문에 뒷부분이
# 통째로 기울임체가 되어버리는 등 예상치 못한 모양으로 렌더링된다.
# 그래서 여러 줄/특수문자가 섞인 title을 한 줄로 보여줘야 하는 곳에서는
# 항상 이 함수로 먼저 다듬는다. (상세 설명(description)은 원래 여러 줄이
# 자연스러워서 여기서 건드리지 않는다.)
def _clean_title(text:str) -> str:
    collapsed = " ".join(text.split())

    for ch in ("\\", "*", "_", "`"):  # 마지막은 백틱(`) - 홑따옴표(')가 아니라
        # 마크다운 특수문자 앞에 \를 붙여서 "문법"이 아니라 "글자 그대로"
        # 렌더링되게 만든다 (예: "_" -> "\_"). \\부터 먼저 처리해야 나중에
        # 붙이는 \가 또 escape 대상이 되는 걸 막을 수 있다.
        collapsed = collapsed.replace(ch, "\\" + ch)
    return collapsed
    # text.split()은 공백/줄바꿈 종류와 개수에 상관없이 단어 단위로 쪼개고, "".join(...)이 그 단어들을 스페이스 하나로단 다시 이어 붙임
    #줄바꿈이 전부 사라지고 한 줄짜리 문장이 된다

# ---- 헬퍼: 활동 카드 하나를 그리는 함수 --------------------------------
# "단계별 목록"과 "검색 결과 목록"에서 활동 카드를 똑같은 모양으로 그려야
# 해서, 반복되는 부분을 함수로 뽑아뒀다. phase_name을 넘기면 카드 제목에
# 어느 단계의 활동인지도 같이 표시한다 (검색 결과는 여러 단계가 섞이므로).
def _render_activity_card(act: dict, phase_name: str | None = None) -> None:
    label = f"**{act['id']}** {_clean_title(act['title'])}"
    if phase_name:
        label += f"  _{phase_name}_"
    with st.expander(label):
        if act.get("description"):
            st.markdown(act["description"])
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**산출물**")
            deliverable = act.get("deliverable") or {}
            st.write(deliverable.get("name") or "-")
            if deliverable.get("input_ref"):
                st.caption(f"참고 입력자료: {deliverable['input_ref']}")

            st.markdown("**필요 역량**")
            skills = act.get("required_skills") or []
            st.write(", ".join(skills) if skills else "-")

        with col2:
            st.markdown("**품질팀 역할 (R&R)**")
            role = act.get("quality_role") or {}

            # 값이 있는(None/빈문자열이 아닌) 역할만 화면에 낼 줄로 모은다
            role_lines = []
            if role.get("guiding"):
                role_lines.append(f"- Guiding: {role['guiding']}")
            if role.get("doing"):
                role_lines.append(f"- Doing: {role['doing']}")
            if role.get("feedback"):
                role_lines.append(f"- Feed-Back: {role['feedback']}")

            if role_lines:
                st.write("\n".join(role_lines))
            else:
                # 세 값이 다 비어있는 경우에만 "-"로 표시
                st.write("-")

            flags = []
            if act.get("repeat_per_phase"):
                flags.append("단계별 반복")
            if act.get("remote_support_possible"):
                flags.append("비상주 지원 가능")
            if flags:
                st.caption(" · ".join(flags))

# ---- 사이드바: 1) 유형 선택 / 2) 단계 선택 / 3) 용어사전 --------------
st.sidebar.title("🧭 품질 온보딩 네비게이터")
st.sidebar.caption("SI 신규 입사자를 위한 유형·단계별 품질 가이드")

st.sidebar.subheader("1. 유형 선택")
project_types = get_project_types(data)
type_labels = [t["name"] for t in project_types]
selected_type_label = st.sidebar.selectbox("프로젝트 유형", type_labels)
selected_type = next(t for t in project_types if t["name"] == selected_type_label)
st.sidebar.caption(selected_type.get("description", ""))

st.sidebar.subheader("2. 단계 선택")
phases = get_phases(data, selected_type["id"])

if not phases:
    st.sidebar.warning("이 유형에는 아직 등록된 단계가 없습니다.")
    st.stop()

phase_labels = [p["name"] for p in phases]
selected_phase_label = st.sidebar.radio("단계", phase_labels)
selected_phase = next(p for p in phases if p["name"] == selected_phase_label)

st.sidebar.divider()

# ---- 사이드바: 3) 용어사전 (버튼만 - 실제 내용은 오른쪽 본문에 뜬다) ----
# 용어사전은 유형·단계와 상관없이 항상 똑같은 내용을 보여준다. 그런데 예전
# 구조에서는 본문 탭 중 하나였어서, 단계를 눌러 바꿔도 용어사전 탭 내용이
# 그대로인 게 "이 단계에만 해당하는 용어인가?"하는 혼란을 줄 수 있었다.
# 그 다음엔 사이드바 안에 통째로 넣어봤는데, 좁은 사이드바 폭에 검색 결과와
# 관리자 모드까지 다 들어가니 너무 좁고 답답했다. 그래서 이번엔 사이드바에는
# 체크박스(스위치)만 두고, 실제 용어사전 화면은 오른쪽 본문 영역에 크게
# 띄우기로 했다.
st.sidebar.subheader("3. 용어사전")
show_glossary = st.sidebar.checkbox("📖 용어사전 보기", key="show_glossary")
st.sidebar.caption("체크하면 오른쪽 화면이 용어사전으로 바뀝니다.")

# ---- 본문: 용어사전(체크 시) 또는 3) 가이드 조회 / 4) 셀프체크 --------
if show_glossary:
    # ---- 제목 + 관리자 모드를 한 줄에 배치 ----
    # 예전엔 관리자 모드가 제목 밑에 가로로 긴 expander라서 화면을 위아래로
    # 길게 차지했다. st.columns로 오른쪽에 좁은 칸을 하나 만들고, 그 안에
    # st.popover(버튼처럼 생긴 작은 트리거)를 넣으면 평소엔 작은 버튼 하나만
    # 보이다가 눌렀을 때만 코드 입력 폼이 떠서 화면이 훨씬 깔끔해진다.
    col_title, col_admin = st.columns([5, 1])
    with col_title:
        st.title("📖 용어사전")
        st.caption("모르는 용어를 검색하시오. 검색어를 비워두면 전체 목록이 보입니다.")
    with col_admin:
        with st.popover("🔒 관리자", width="stretch"):
            st.caption("실수로 용어사전이 바뀌는 걸 막기 위한 정도의 장치입니다. 보안 목적으로 쓰지 마세요.")
            admin_input = st.text_input("관리자 코드", type="password", key="admin_code")
            is_admin = bool(admin_input) and admin_input == ADMIN_CODE

            if admin_input and not is_admin:
                st.error("코드가 올바르지 않습니다.")
            elif is_admin:
                st.success("관리자 모드가 켜졌습니다. 아래 목록에서 수정·삭제할 수 있습니다.")

                st.markdown("**➕ 새 용어 추가**")
                with st.form("add_glossary_form", clear_on_submit=True):
                    new_term = st.text_input("용어명")
                    new_def = st.text_area("설명")
                    submitted = st.form_submit_button("추가")

                if submitted:
                    if not new_term.strip() or not new_def.strip():
                        st.warning("용어명과 설명을 모두 입력해주세요.")
                    else:
                        add_glossary_term(data, new_term.strip(), new_def.strip())
                        save_data(data)
                        load_data.cache_clear()
                        # cache_clear()로 load_data의 캐시를 지워야, st.rerun() 뒤
                        # 다시 실행될 때 방금 저장한 파일을 새로 읽어온다.
                        st.success(f"'{new_term}' 용어가 추가되었습니다.")
                        st.rerun()

    glossary_keyword = st.text_input(
        "검색어", placeholder="예: RFP, 감리, 게이트 등", key="glossary_search"
    )
    glossary_results = search_glossary(data, glossary_keyword)

    # ---- 검색 결과 목록 (+ 관리자 모드면 수정/삭제 UI) ----
    if not glossary_results:
        st.warning(f"'{glossary_keyword}'에 해당하는 용어를 찾지 못했습니다.")
    else:
        st.write(f"**{len(glossary_results)}개** 용어")
        for g in glossary_results:
            st.markdown(f"**{g['term']}**")
            st.write(g["definition"])

            if is_admin:
                with st.expander(f"'{g['term']}' 수정 / 삭제"):
                    with st.form(f"edit_form_{g['id']}"):
                        edit_term = st.text_input("용어명", value=g["term"])
                        edit_def = st.text_area("설명", value=g["definition"])
                        save_clicked = st.form_submit_button("저장")

                    if save_clicked:
                        update_glossary_term(
                            data, g["id"], term=edit_term.strip(), definition=edit_def.strip()
                        )
                        save_data(data)
                        load_data.cache_clear()
                        st.success("수정되었습니다.")
                        st.rerun()

                    st.divider()

                    # ---- 삭제 확인 단계 ----
                    # 삭제는 되돌릴 수 없는 작업이라, 버튼을 폼 밖으로 빼서
                    # session_state 플래그로 "정말 삭제하시겠습니까?"를 한 번 더
                    # 물어본 뒤에만 실제로 지운다.
                    confirm_key = f"confirm_delete_{g['id']}"

                    if not st.session_state.get(confirm_key, False):
                        if st.button("삭제", key=f"delete_btn_{g['id']}"):
                            st.session_state[confirm_key] = True
                            st.rerun()
                    else:
                        st.warning(
                            f"'{g['term']}' 용어를 정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다."
                        )
                        col_yes, col_no = st.columns(2)
                        if col_yes.button("네, 삭제합니다", key=f"confirm_yes_{g['id']}"):
                            delete_glossary_term(data, g["id"])
                            save_data(data)
                            load_data.cache_clear()
                            st.session_state[confirm_key] = False
                            st.success(f"'{g['term']}'이 삭제되었습니다.")
                            st.rerun()
                        if col_no.button("취소", key=f"confirm_no_{g['id']}"):
                            st.session_state[confirm_key] = False
                            st.rerun()

            st.divider()

else:
    # ---- 제목 + 활동 관리자 모드를 한 줄에 배치 ----
    # 용어사전과 같은 이유로, "활동 내용 수정·삭제" 관리자 모드도 제목 옆
    # 오른쪽 위에 작은 버튼(popover)으로 옮겼다. is_activity_admin은 여기서
    # 한 번만 계산해두면 아래 탭(특히 셀프 체크)에서도 그대로 쓸 수 있다 -
    # with 블록이나 탭은 새로운 변수 범위를 만들지 않기 때문이다.
    col_title, col_admin = st.columns([5, 1])
    with col_title:
        st.title(f"{selected_type['name']} · {selected_phase['name']}")
        st.caption(f"대분류: {selected_phase.get('group', '-')}")
    with col_admin:
        with st.popover("🔒 관리자", width="stretch"):
            st.caption("이 프로젝트에 맞지 않는 활동의 제목/설명을 바꾸거나 삭제할 때 씁니다. 보안 목적이 아닙니다.")
            activity_admin_input = st.text_input(
                "관리자 코드", type="password", key="activity_admin_code"
            )
            is_activity_admin = bool(activity_admin_input) and activity_admin_input == ADMIN_CODE
            if activity_admin_input and not is_activity_admin:
                st.error("코드가 올바르지 않습니다.")

    tab_guide, tab_check = st.tabs(["📋 가이드 조회", "✅ 셀프 체크"])

    with tab_guide:
        guide_keyword = st.text_input(
            "활동 검색",
            placeholder="예: RFP, 검토, 산출물 ... (제목·설명에서 검색, 선택한 유형 전체 대상)",
            key="guide_search",
        )

        if guide_keyword.strip():
            # 검색어가 있으면 "선택한 단계"와 무관하게 유형 전체(8개 단계, 94개 활동)를
            # 대상으로 검색한다. 어디에 있는 활동인지 헷갈리지 않게 단계명을 같이 보여준다.
            phase_name_by_id = {p["id"]: p["name"] for p in phases}
            results = search_activities(data, selected_type["id"], guide_keyword)

            if not results:
                st.warning(f"'{guide_keyword}'에 해당하는 활동을 찾지 못했습니다.")
            else:
                st.write(f"**{selected_type['name']}** 전체에서 **{len(results)}개** 활동 검색됨")
                for act in results:
                    _render_activity_card(act, phase_name=phase_name_by_id.get(act["phase_id"]))
        else:
            # 검색어가 없으면 기존처럼 사이드바에서 고른 단계의 활동만 보여준다
            activities = get_activities(data, selected_phase["id"])

            if not activities:
                st.info("이 단계에는 아직 등록된 활동이 없습니다.")
            else:
                st.write(f"총 **{len(activities)}개** 활동")
                for act in activities:
                    _render_activity_card(act)

    with tab_check:
        # 체크 상태의 "진짜 저장소"는 checked_activity_ids(set)다. 체크박스
        # 자신의 key(check_활동id)에는 더 이상 의존하지 않는다 - 다른 단계로
        # 넘어가서 그 체크박스가 화면에 안 그려지는 동안 Streamlit이 위젯
        # 값을 보존해주지 않는 경우가 있어서, 그 때문에 "다른 단계를 눌렀다가
        # 돌아오면 체크가 풀려있는" 문제가 있었다.

        # 진행률 계산은 "현재 선택한 유형 전체"를 기준으로 한다 (단계 하나만 보면
        # 방금 다른 단계에서 체크한 것들이 반영이 안 된 것처럼 보이기 때문).

        all_type_activities = get_all_activities(data, selected_type["id"])

        def _is_done(activity_id: str) -> bool:
            # checked_activity_ids는 위젯이 그려지든 안 그려지든(다른 단계를
            # 보고 있어도) 항상 남아있는 "진짜 저장소"다. 체크박스 자신의
            # key(check_활동id)를 더 이상 참조하지 않는다.
            return activity_id in st.session_state.get("checked_activity_ids", set())

        def _is_overdue(activity_id: str) -> bool:
            # 마감일이 설정돼 있고, 그 날짜가 오늘보다 이전이고, 아직 완료
            # 체크가 안 됐으면 "기한 초과"로 본다. 완료된 활동은 마감일이
            # 지났어도 알람을 띄우지 않는다(이미 끝났으니까).
            due = st.session_state.get("activity_due_dates", {}).get(activity_id)
            return bool(due) and due < date.today() and not _is_done(activity_id)

        # ---- 진행률 요약(전체 진행률/카드/차트)은 자리만 먼저 잡아둔다 ----
        # 체크박스를 누르면 그 값은 즉시 checked_activity_ids에 반영되지만,
        # 이 요약 숫자들은 "활동 체크 목록"을 다 그린 다음에 계산해야 방금
        # 누른 체크가 곧바로 반영된다(먼저 계산해버리면 이번 클릭 이전
        # 상태로 한 번 더 그려지고, 그 다음 클릭에야 따라잡는 버그가 있었다).
        # st.container()로 화면상 자리는 위쪽에 미리 예약해두고, 실제 내용은
        # 아래에서 체크리스트를 그린 "다음"에 이 자리에 채워 넣는다.
        dashboard_area = st.container()

        st.divider()

        only_incomplete = st.checkbox("미완료 항목만 보기", value = False)
        st.markdown(f"**{selected_phase['name']}**단계 활동 체크")
        phase_activities = get_activities(data, selected_phase["id"])

        if not phase_activities:
            st.info("이 단계에는 아직 등록된 활동이 없습니다")
        else:
            for act in phase_activities:
                # 필터링은 위젯을 그리기도 전에 걸러내야 하므로, 진짜 저장소
                # (checked_activity_ids)에 남아있는 "이번 실행 시작 시점" 값으로
                # 판단한다.
                act_done_for_filter = act["id"] in st.session_state["checked_activity_ids"]

                if only_incomplete and act_done_for_filter:
                    #미완료 항목만 보기가 켜져 있고 이미 완료된 활동이면 건너뛴다
                    continue

                col_check, col_label, col_due = st.columns([1, 6, 3])

                # ---- 체크박스/마감일을 먼저 그리고 진짜 저장소에 반영한다 ----
                # 체크박스/날짜 위젯 자신의 key(check_활동id, due_활동id)는
                # "지금 화면에 뭘 보여줄지" 용도로만 쓰고, 위젯이 돌려주는 값을
                # 곧바로 checked_activity_ids/activity_due_dates(진짜 저장소)에
                # 반영한다. 그래야 다른 단계로 넘어가서 이 위젯이 한동안 안
                # 그려지더라도 체크/마감일이 사라지지 않는다. 그리고 아이콘/
                # 알람(col_label)은 이 두 위젯을 처리한 "다음"에 계산해야
                # 한다 - 순서를 반대로 하면 방금 체크하거나 마감일을 바꾼
                # 직후 한 번은 아이콘이 옛 상태로 보이는 버그가 생긴다(코멘트
                # 상태 아이콘에서 있었던 것과 같은 원인). 화면 배치(왼쪽 체크,
                # 가운데 제목, 오른쪽 마감일)는 코드 순서와 무관하게 유지된다.
                with col_check:
                    checked_now = st.checkbox(
                        "완료",
                        value=act_done_for_filter,
                        key=f"check_{act['id']}",
                        label_visibility="collapsed",
                    )
                    if checked_now:
                        st.session_state["checked_activity_ids"].add(act["id"])
                    else:
                        st.session_state["checked_activity_ids"].discard(act["id"])

                with col_due:
                    due_before = st.session_state["activity_due_dates"].get(act["id"])

                    # st.date_input 자체에는 "날짜를 아예 지우는" 버튼이 없거나
                    # 잘 눌리지 않는 버전이 있어서(날짜만 바뀌고 삭제가 안 됨),
                    # 마감일이 있을 때만 옆에 삭제 버튼(✕)을 따로 둔다.
                    sub_date, sub_clear = st.columns([4, 1])

                    with sub_date:
                        due_input = st.date_input(
                            "마감일",
                            value=due_before,
                            key=f"due_{act['id']}",
                            format="YYYY-MM-DD",
                            label_visibility="collapsed",
                        )

                    with sub_clear:
                        if due_before and st.button(
                            "✕", key=f"clear_due_{act['id']}", help="마감일 삭제"
                        ):
                            # 진짜 저장소(activity_due_dates)에서 지우는 것만으로는
                            # 부족하다 - date_input 위젯 자신의 key에 값이 남아있으면
                            # 다음에 그려질 때 그 값을 그대로 다시 보여준다. 위젯의
                            # key도 같이 지우고 즉시 rerun해야 입력창이 진짜 빈
                            # 상태로 리셋된다.
                            st.session_state["activity_due_dates"].pop(act["id"], None)
                            st.session_state.pop(f"due_{act['id']}", None)
                            st.rerun()

                    if due_input:
                        st.session_state["activity_due_dates"][act["id"]] = due_input
                    else:
                        st.session_state["activity_due_dates"].pop(act["id"], None)

                act_done = act["id"] in st.session_state["checked_activity_ids"]
                due_value = st.session_state["activity_due_dates"].get(act["id"])
                is_overdue = bool(due_value) and due_value < date.today() and not act_done

                if act_done:
                    icon = "✅"
                elif is_overdue:
                    icon = "⏰"
                else:
                    icon = "🔲"

                with col_label:
                    # act['title']을 그대로 쓰면 줄바꿈/밑줄 때문에 마크다운이 깨진다.
                    # _render_activity_card와 마찬가지로 _clean_title로 다듬어야 한다.
                    title = _clean_title(act["title"])
                    if act_done:
                        st.markdown(f"{icon} {act['id']}  {title}")
                    else:
                        # 미완료 항목은 굵게 강조해서 눈에 잘 띄게 한다
                        st.markdown(f"{icon} **{act['id']}  {title}**")

                    if is_overdue:
                        # Airbnb 디자인의 에러 텍스트 색(#c13515)을 그대로 써서
                        # 앱 전체 색 톤과 어긋나지 않게 했다.
                        st.markdown(
                            f'<span style="color:#c13515; font-weight:600; font-size:13px;">'
                            f"⏰ 기한 초과 (마감 {due_value.isoformat()})</span>",
                            unsafe_allow_html=True,
                        )

                # ---- 활동별 코멘트 / 추가 업무 (여러 개 계속 추가 가능) ----
                # 예전엔 st.text_input 한 줄이라 코멘트를 새로 적으면 이전
                # 내용을 덮어썼다. 이제는 "추가 업무"처럼 목록 형태로 만들어서,
                # 코멘트/할 일을 계속 쌓아가며 각각 진행 중/완료 상태까지 관리할
                # 수 있게 했다. session_state[f"notes_{활동id}"]에 세션 한정으로
                # 저장된다(새로고침하면 초기화, 파일에는 저장되지 않음).
                notes_key = f"notes_{act['id']}"
                if notes_key not in st.session_state:
                    st.session_state[notes_key] = []
                notes = st.session_state[notes_key]

                with st.expander(f"💬 코멘트 / 추가 업무 ({len(notes)})"):
                    with st.form(f"add_note_form_{act['id']}", clear_on_submit=True):
                        new_note_text = st.text_input(
                            "새 코멘트", placeholder="예: 고객사 검토 대기 중"
                        )
                        add_note_submitted = st.form_submit_button("추가")

                    if add_note_submitted:
                        if not new_note_text.strip():
                            st.warning("내용을 입력해주세요.")
                        else:
                            notes.append(
                                {
                                    "id": str(uuid.uuid4()),
                                    "text": new_note_text.strip(),
                                    "status": "진행 중",
                                }
                            )
                            st.rerun()

                    if not notes:
                        st.caption("아직 등록된 코멘트/추가 업무가 없습니다.")
                    else:
                        for note in notes:
                            col_note_text, col_note_status, col_note_delete = st.columns([6, 2, 1])

                            # 드롭다운(상태)을 먼저 처리해서 note["status"]를 갱신한
                            # 다음에 아이콘을 그린다. 순서를 반대로 하면(아이콘을 먼저
                            # 그리고 드롭다운을 나중에 갱신하면) 방금 "완료"로 바꾼
                            # 직후 한 번은 아이콘이 옛 상태(🔵)로 그려지는 버그가
                            # 있었다 - 코드에서 쓰는 순서일 뿐 화면 배치(왼쪽 col_note_text,
                            # 오른쪽 col_note_status)는 그대로 유지된다.
                            with col_note_status:
                                new_note_status = st.selectbox(
                                    "상태",
                                    ["진행 중", "완료"],
                                    index=["진행 중", "완료"].index(note["status"]),
                                    key=f"note_status_{note['id']}",
                                    label_visibility="collapsed",
                                )
                                note["status"] = new_note_status

                            with col_note_text:
                                note_icon = "✅" if note["status"] == "완료" else "🔵"
                                st.write(f"{note_icon} {note['text']}")

                            with col_note_delete:
                                if st.button("🗑️", key=f"delete_note_{note['id']}"):
                                    st.session_state[notes_key] = [
                                        n for n in notes if n["id"] != note["id"]
                                    ]
                                    st.rerun()

                # ---- 관리자 모드: 이 활동 내용 수정 / 삭제 ----
                # "1-1-7 활동이 이번 프로젝트엔 없고 다른 1-1-7 활동이 들어간다"
                # 같은 경우, id는 그대로 두고 제목/설명만 바꿔서 대체하거나
                # 아예 삭제할 수 있게 한다.
                if is_activity_admin:
                    with st.expander(f"✏️ '{act['id']}' 활동 수정 · 삭제"):
                        with st.form(f"edit_activity_form_{act['id']}"):
                            edit_title = st.text_input("제목", value=act["title"])
                            edit_desc = st.text_area(
                                "설명", value=act.get("description") or ""
                            )
                            save_activity_clicked = st.form_submit_button("저장")

                        if save_activity_clicked:
                            update_activity(
                                data, act["id"], title=edit_title.strip(), description=edit_desc.strip()
                            )
                            save_data(data)
                            load_data.cache_clear()
                            st.success("수정되었습니다.")
                            st.rerun()

                        st.divider()

                        # ---- 삭제 확인 단계 (글로서리 삭제와 동일한 패턴) ----
                        confirm_activity_key = f"confirm_delete_activity_{act['id']}"

                        if not st.session_state.get(confirm_activity_key, False):
                            if st.button("이 활동 삭제", key=f"delete_activity_btn_{act['id']}"):
                                st.session_state[confirm_activity_key] = True
                                st.rerun()
                        else:
                            st.warning(
                                f"'{act['id']}' 활동을 정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다."
                            )
                            col_act_yes, col_act_no = st.columns(2)
                            if col_act_yes.button(
                                "네, 삭제합니다", key=f"confirm_activity_yes_{act['id']}"
                            ):
                                delete_activity(data, act["id"])
                                save_data(data)
                                load_data.cache_clear()
                                st.session_state[confirm_activity_key] = False
                                st.success(f"'{act['id']}' 활동이 삭제되었습니다.")
                                st.rerun()
                            if col_act_no.button("취소", key=f"confirm_activity_no_{act['id']}"):
                                st.session_state[confirm_activity_key] = False
                                st.rerun()

                st.divider()

        # ---- 진행률 요약을 이제서야 계산해서 위에 예약해둔 자리에 채운다 ----
        # 여기까지 오면 방금 이 실행에서 눌린 체크박스/마감일이 모두
        # checked_activity_ids/activity_due_dates에 반영된 뒤이므로, 이제
        # total/done/ratio 등을 계산하면 "이번 클릭"이 곧바로 숫자와
        # 차트에 반영된다(예전엔 이 계산이 체크리스트보다 먼저 있어서
        # 한 클릭씩 뒤처져 보였다).
        total = len(all_type_activities)
        done = sum(1 for a in all_type_activities if _is_done(a["id"]))
        ratio = done / total if total else 0.0
        overdue_count = sum(1 for a in all_type_activities if _is_overdue(a["id"]))

        phase_stats = []
        for p in phases:
            p_activities = get_activities(data, p["id"])
            p_total = len(p_activities)
            p_done = sum(1 for a in p_activities if _is_done(a["id"]))
            p_ratio = p_done / p_total if p_total else 0.0
            phase_stats.append({"phase": p, "total": p_total, "done": p_done, "ratio": p_ratio})

        phases_done = sum(1 for s in phase_stats if s["total"] > 0 and s["done"] == s["total"])
        phases_in_progress = sum(1 for s in phase_stats if 0 < s["done"] < s["total"])
        phases_not_started = sum(1 for s in phase_stats if s["done"] == 0)

        with dashboard_area:
            st.subheader(f"{selected_type['name']} 전체 진행률")
            st.markdown(_progress_bar_html(ratio, height=14), unsafe_allow_html=True)
            st.caption(f"{done} / {total} 완료 ({ratio * 100:.0f}%)")

            card1, card2, card3, card4, card5 = st.columns(5)
            card1.metric("전체 진행률", f"{ratio * 100:.0f}%")
            card2.metric("완료 단계", f"{phases_done} / {len(phases)}")
            card3.metric("진행 중", phases_in_progress)
            card4.metric("시작 전", phases_not_started)
            card5.metric("⏰ 기한 초과", overdue_count)

            with st.expander("단계별 진행률 보기", expanded=True):
                # 예전엔 st.progress 스타일 막대를 8줄 나열했는데, 숫자/막대를
                # 한 줄씩 읽어야 비교가 됐다. 막대그래프 하나로 모아 그리면 길이
                # 차이만으로 단계 간 진행률을 한눈에 비교할 수 있어서, 여기서부터는
                # 직접 만든 HTML 막대 대신 Altair 차트(Streamlit에 기본 포함된
                # 라이브러리)로 그린다. 색은 상태(완료/진행 중/시작 전/활동 없음)를
                # 나타내고, 지금 사이드바에서 고른 단계는 이름 앞에 👉를 붙여
                # 표시한다(차트를 클릭해서 이동하는 기능은 아니다).
                chart_rows = []
                for s in phase_stats:
                    p, p_total, p_done, p_ratio = s["phase"], s["total"], s["done"], s["ratio"]

                    if p_total == 0:
                        status_label = "활동 없음"
                    elif p_done == 0:
                        status_label = "시작 전"
                    elif p_done == p_total:
                        status_label = "완료"
                    else:
                        status_label = "진행 중"

                    is_current = p["id"] == selected_phase["id"]
                    chart_rows.append(
                        {
                            "단계": f"{'👉 ' if is_current else ''}{p['name']}",
                            "순서": p["order"],
                            "진행률": round(p_ratio * 100),
                            "상태": status_label,
                            "완료/전체": f"{p_done}/{p_total}",
                        }
                    )

                chart_df = pd.DataFrame(chart_rows)
                phase_order = chart_df.sort_values("순서")["단계"].tolist()

                # 막대 높이(size)를 고정 픽셀로 주는 대신, 차트 전체 높이를
                # 단계 수에 맞춰 넉넉하게 잡고 행 사이 간격(paddingInner)도
                # 줘야 한다 - 예전엔 차트 높이가 기본값(고정)이라 단계가
                # 늘어날수록 한 행에 배정되는 공간이 막대 두께보다 작아져서
                # 옆 줄 막대끼리 맞붙어 하나의 막대처럼 보이는 문제가 있었다.
                row_height = 34
                chart_height = max(200, len(phase_stats) * row_height)

                bars = (
                    alt.Chart(chart_df)
                    .mark_bar(cornerRadiusEnd=4, size=row_height * 0.6)
                    .encode(
                        x=alt.X("진행률:Q", scale=alt.Scale(domain=[0, 100]), title="진행률 (%)"),
                        y=alt.Y(
                            "단계:N",
                            sort=phase_order,
                            title=None,
                            scale=alt.Scale(paddingInner=0.35, paddingOuter=0.2),
                        ),
                        color=alt.Color(
                            "상태:N",
                            scale=alt.Scale(
                                domain=["완료", "진행 중", "시작 전", "활동 없음"],
                                range=["#0ca30c", "#ff385c", "#c1c1c1", "#e5e5e5"],
                            ),
                            legend=alt.Legend(title="상태"),
                        ),
                        tooltip=["단계", "상태", "진행률", "완료/전체"],
                    )
                    .properties(height=chart_height)
                )
                labels = bars.mark_text(align="left", dx=4).encode(
                    text=alt.Text("진행률:Q", format=".0f")
                )

                st.altair_chart(bars + labels, width="stretch")

        if only_incomplete and done == total and total > 0:
            st.success("이 유형의 모든 활동을 완료했습니다! 🎉")

# ---- 셀프체크 진행 상황 저장 ----------------------------------------
# if/else(용어사전 화면 vs 가이드/셀프체크 화면) 분기와 무관하게 스크립트가
# 실행될 때마다 맨 마지막에 한 번 호출한다. 용어사전 화면을 보고 있을 때도
# 어차피 체크 상태 자체는 안 바뀌니 저장해도 그대로고, 셀프체크에서 뭔가
# 바꾼 뒤라면 이 호출로 그 최신 상태가 파일에 반영된다.
_persist_progress()