import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 일일 박스오피스 · 한국 시간 기준")


# ---------------------------------------------------------
# 2. 한국 시간으로 '어제' 날짜 계산
# ---------------------------------------------------------
# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있으므로
# 서버의 현재 시간을 그대로 사용하지 않고 KST를 명시합니다.

KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(KST).date()
yesterday_kst = today_kst - timedelta(days=1)

# KOBIS가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday_kst.strftime("%Y%m%d")

# 화면에 보여 줄 날짜 형식
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 3. KOBIS API 주소
# ---------------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 4. KOBIS API 호출 함수
# ---------------------------------------------------------
# ttl=3600은 같은 날짜의 결과를 약 1시간 동안 기억한다는 뜻입니다.
# 따라서 새로고침해도 한 시간 동안 API를 다시 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt: str):
    # Streamlit Cloud의 Secrets에서 인증키를 읽습니다.
    # 실제 인증키를 코드에 직접 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except KeyError:
        return {
            "ok": False,
            "error_type": "secret",
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다. "
                "Streamlit Cloud의 Settings → Secrets에 "
                "KOBIS_KEY가 정확히 등록되어 있는지 확인해 주세요."
            ),
        }

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "error_type": "request",
            "message": (
                "KOBIS API에 요청하는 중 문제가 발생했습니다. "
                "인터넷 연결, KOBIS API 주소, API 서버 상태를 확인해 주세요."
            ),
            "detail": str(e),
        }

    except ValueError:
        return {
            "ok": False,
            "error_type": "json",
            "message": (
                "KOBIS에서 예상한 JSON 형식의 응답을 받지 못했습니다. "
                "잠시 후 다시 시도하거나 KOBIS API 상태를 확인해 주세요."
            ),
        }

    # 인증키가 틀린 경우에도 HTTP 상태코드는 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
    if "faultInfo" in data:
        fault_info = data.get("faultInfo", {})

        return {
            "ok": False,
            "error_type": "fault",
            "message": (
                "KOBIS API에서 오류를 반환했습니다. "
                "인증키(KOBIS_KEY)가 올바른지, API 사용 설정이 되어 있는지 "
                "확인해 주세요."
            ),
            "detail": fault_info,
        }

    # 정상적인 응답이라면 boxOfficeResult를 확인합니다.
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "ok": False,
            "error_type": "empty_result",
            "message": (
                "KOBIS 응답에 boxOfficeResult가 없습니다. "
                "조회 날짜와 KOBIS API 응답을 확인해 주세요."
            ),
        }

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있으면 사용자에게 확인할 내용을 안내합니다.
    if not movie_list:
        return {
            "ok": False,
            "error_type": "empty_list",
            "message": (
                f"{target_dt} 날짜의 영화 목록이 비어 있습니다. "
                "해당 날짜의 박스오피스 집계 여부와 KOBIS API 상태를 "
                "확인해 주세요."
            ),
        }

    return {
        "ok": True,
        "movies": movie_list,
    }


# ---------------------------------------------------------
# 5. API 결과 가져오기
# ---------------------------------------------------------

result = get_boxoffice(target_date)


# ---------------------------------------------------------
# 6. 오류 처리
# ---------------------------------------------------------

if not result["ok"]:
    st.error("박스오피스 데이터를 가져오지 못했습니다.")
    st.warning(result["message"])

    # 개발자가 원인을 파악할 때 도움이 되도록
    # API가 반환한 상세 오류가 있으면 접어서 보여 줍니다.
    if result.get("detail"):
        with st.expander("오류 상세 정보"):
            st.write(result["detail"])

    st.stop()


# ---------------------------------------------------------
# 7. 숫자 문자열을 실제 숫자로 변환
# ---------------------------------------------------------
# KOBIS API에서는 rank, audiCnt 등의 값도 문자열로 옵니다.
# 그래프와 정렬에 제대로 사용하기 위해 정수로 변환합니다.

movies = []

for movie in result["movies"]:
    converted_movie = movie.copy()

    converted_movie["rank"] = int(movie.get("rank", 0))
    converted_movie["rankInten"] = int(movie.get("rankInten", 0))
    converted_movie["audiCnt"] = int(movie.get("audiCnt", 0))
    converted_movie["audiAcc"] = int(movie.get("audiAcc", 0))
    converted_movie["scrnCnt"] = int(movie.get("scrnCnt", 0))
    converted_movie["showCnt"] = int(movie.get("showCnt", 0))

    movies.append(converted_movie)


# 순위를 기준으로 다시 정렬합니다.
movies.sort(key=lambda x: x["rank"])


# ---------------------------------------------------------
# 8. 조회 날짜 표시
# ---------------------------------------------------------

st.subheader(f"📅 {display_date}")
st.caption("※ '어제'는 한국 표준시(KST)를 기준으로 계산했습니다.")


# ---------------------------------------------------------
# 9. 1위 영화 지표 카드
# ---------------------------------------------------------

first_movie = movies[0]

st.markdown("### 🥇 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="영화",
        value=first_movie["movieNm"],
    )

with col2:
    st.metric(
        label="관객수",
        value=f'{first_movie["audiCnt"]:,}명',
    )

with col3:
    st.metric(
        label="스크린수",
        value=f'{first_movie["scrnCnt"]:,}개',
    )


# ---------------------------------------------------------
# 10. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
# 영화가 5편보다 적은 경우에는 있는 영화만 사용합니다.

st.markdown("### 📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda x: x["audiCnt"],
    reverse=True,
)[:5]

# Streamlit의 bar_chart에 넣을 수 있도록
# 영화명을 인덱스로 하고 관객수를 숫자 컬럼으로 만듭니다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}

st.bar_chart(chart_data, horizontal=True)


# ---------------------------------------------------------
# 11. 전체 박스오피스 표
# ---------------------------------------------------------

st.markdown("### 🎞️ 전체 박스오피스")

table_data = []

for movie in movies:
    table_data.append(
        {
            "순위": movie["rank"],
            "영화명": movie["movieNm"],
            "개봉일": movie["openDt"],
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%,d",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%,d",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%,d",
        ),
    },
)


# ---------------------------------------------------------
# 12. 데이터 출처
# ---------------------------------------------------------

st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS) 일일 박스오피스 API"
)
