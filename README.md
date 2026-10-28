품질 온보딩 네비게이터 (Quality Onboarding Navigator)

SI(시스템 통합) 프로젝트에 새로 투입된 신입/경력 품질(QE) 담당자가 "이 프로젝트 유형에서, 이 단계에서, 내가 뭘 해야 하는지"를 한눈에 찾아볼 수 있게 만든 셀프 온보딩 도구입니다. 여러 곳에 흩어진 품질 활동 가이드를 하나의 화면에서 조회하고, 자신의 진행 상황을 체크·기록할 수 있습니다.

Python + Streamlit으로 만든 웹 앱이며, 데이터는 SQLite DB 파일 하나에 저장됩니다.

주요 기능
유형 선택: 신규 / 고도화·전환 / SM / AI 적용 중 현재 투입된 프로젝트 유형을 선택합니다.
단계 선택: 착수부터 종료까지, 선택한 유형에 속한 단계를 사이드바에서 고릅니다.
가이드 조회: 선택한 단계의 품질 활동 목록을 산출물, 역할(가이드/수행/피드백), 필요 역량, 반복 여부와 함께 확인합니다. 키워드로 유형 전체를 검색할 수도 있습니다.
셀프 체크: 활동별로 완료 체크, 마감일 설정(기한 초과 시 알람 표시), 코멘트/추가 업무를 여러 개 계속 추가하며 상태(진행 중/완료)를 관리합니다. 전체·단계별 진행률을 카드와 막대 차트로 한눈에 비교할 수 있습니다.
용어사전: SI 프로젝트에서 자주 쓰이는 용어(RFP, Sign-off 등)를 검색해서 찾아봅니다.
관리자 모드: 각 화면 우측 상단의 "🔒 관리자" 버튼을 통해, 코드를 입력하면 용어사전 추가·수정·삭제, 활동 내용 수정·삭제가 가능합니다. (실수로 데이터가 바뀌는 걸 막기 위한 장치일 뿐, 실제 보안 목적은 아닙니다.)
데이터 영속성: 체크 여부·코멘트·마감일 등 진행 상황은 SQLite DB에 저장되어, 브라우저를 새로고침하거나 앱을 껐다 켜도 유지됩니다.
기술 스택
Streamlit - UI 프레임워크
SQLite (Python 표준 라이브러리 sqlite3) - 데이터 저장소
Altair + pandas - 단계별 진행률 차트
프로젝트 구조
.
├── UI_test.py                              # Streamlit 앱 (화면/상호작용 전체)
├── loader.py                               # 데이터 조회·CRUD·영속성 로직 (SQLite 접근 계층)
├── quality_onboarding_navigator.db         # SQLite DB (활동 데이터 + 셀프체크 진행 상황)
├── quality_onboarding_navigator_data.json  # DB로 옮기기 전 원본 데이터 (백업용, 앱은 더 이상 읽지 않음)
├── .streamlit/config.toml                  # Streamlit 테마 설정
├── requirements.txt                        # 의존 패키지 목록
└── DESIGN.md / airbnb/DESIGN.md             # 참고한 디자인 시스템 문서
데이터 모델

quality_onboarding_navigator.db 안에 아래 테이블이 들어있습니다. DBeaver 같은 SQLite 클라이언트로 직접 열어서 조회·수정할 수 있습니다.

테이블	설명
project_types	프로젝트 유형 (신규/고도화·전환/SM/AI적용)
phases	유형별 단계 (착수~종료)
activities	단계별 품질 활동 (제목, 설명, 산출물, 역할, 필요 역량 등)
glossary	용어사전
progress_checked	체크 완료된 활동 id 목록
progress_due_dates	활동별 마감일
progress_notes	활동별 코멘트/추가 업무 (상태 포함)
실행 방법
bash
pip install -r requirements.txt
streamlit run UI_test.py

loader.py와 quality_onboarding_navigator.db가 UI_test.py와 같은 폴더에 있어야 하며, .streamlit/config.toml은 .streamlit 하위 폴더에 위치해야 Streamlit이 테마를 인식합니다.

개발 배경

사내에 흩어진 품질 활동 가이드를 신입 입장에서 매번 찾아보기 번거롭다는 문제의식에서 출발했습니다. 데이터 스키마 설계 → 로더 구현 → UI 구성 → 셀프체크/용어사전 기능 → 데이터 영속성(JSON → SQLite 전환) 순으로 점진적으로 발전시켰습니다.
