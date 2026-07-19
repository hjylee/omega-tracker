import streamlit as st
import sqlite3
import datetime
import pandas as pd

# ⏰ 한국 시간대(KST) 설정 (UTC+9)
KST = datetime.timezone(datetime.timedelta(hours=9))

# --- DB 연결 및 자동 초기화 ---
def get_connection():
    return sqlite3.connect('tracker.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS Users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS Daily_Logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        log_date DATE NOT NULL,
        morning_prayer BOOLEAN DEFAULT 0,
        daily_bread BOOLEAN DEFAULT 0,
        five_senses BOOLEAN DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES Users(user_id),
        UNIQUE (user_id, log_date)
    )
    ''')
    # 🛠 [추가됨] 주간 기도제목 테이블
    c.execute('''
    CREATE TABLE IF NOT EXISTS Weekly_Prayer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL
    )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 웹 화면 시작 ---
st.title("🌱 본질 사수 트래커")
st.write("매일 새벽기도, 일용할 양식, 오감을 체크해 보세요!")

with st.expander("👤 새로운 DNA원 등록하기"):
    new_name = st.text_input("이름을 입력하세요")
    if st.button("등록"):
        if new_name:
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO Users (name) VALUES (?)", (new_name,))
            conn.commit()
            conn.close()
            st.success(f"'{new_name}'님이 등록되었습니다! 적용을 위해 🔄 새로고침 해주세요.")

conn = get_connection()
users_df = pd.read_sql_query("SELECT user_id, name FROM Users", conn)

if not users_df.empty:
    st.divider()
    
    user_dict = dict(zip(users_df['name'], users_df['user_id']))
    selected_name = st.selectbox("이름을 선택하세요", options=list(user_dict.keys()))
    selected_user_id = user_dict[selected_name]

    today_kst = datetime.datetime.now(KST).date()
    log_date = st.date_input("날짜", today_kst)

    c = conn.cursor()
    c.execute("SELECT morning_prayer, daily_bread, five_senses FROM Daily_Logs WHERE user_id=? AND log_date=?", (selected_user_id, log_date))
    existing_log = c.fetchone()
    
    default_prayer = bool(existing_log[0]) if existing_log else False
    default_bread = bool(existing_log[1]) if existing_log else False
    default_senses = bool(existing_log[2]) if existing_log else False

    st.subheader(f"✅ {log_date} 체크리스트")
    
    morning_prayer = st.checkbox("🙏 새벽기도", value=default_prayer)
    daily_bread = st.checkbox("🍞 일용할 양식", value=default_bread)
    five_senses = st.checkbox("🖐️ 오감", value=default_senses)

    if st.button("저장하기", type="primary"):
        c.execute("""
            INSERT INTO Daily_Logs (user_id, log_date, morning_prayer, daily_bread, five_senses)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, log_date) DO UPDATE SET
                morning_prayer=excluded.morning_prayer,
                daily_bread=excluded.daily_bread,
                five_senses=excluded.five_senses
        """, (selected_user_id, log_date, morning_prayer, daily_bread, five_senses))
        conn.commit()
        st.success("오늘의 기록이 성공적으로 저장되었습니다! 🎉")
else:
    st.info("등록된 DNA원이 없습니다. 위 메뉴에서 이름을 먼저 등록해주세요.")

# --- 3. 주간 통계 대시보드 ---
st.divider()
st.header("📊 주간 통계 대시보드")

today = datetime.datetime.now(KST).date()
start_of_week = today - datetime.timedelta(days=today.weekday())
end_of_week = start_of_week + datetime.timedelta(days=6)

st.write(f"**이번 주 기간:** `{start_of_week}` ~ `{end_of_week}`")

query = """
    SELECT 
        u.name AS '이름',
        IFNULL(SUM(d.morning_prayer), 0) AS '새벽기도 (회)',
        IFNULL(SUM(d.daily_bread), 0) AS '일용할 양식 (회)',
        IFNULL(SUM(d.five_senses), 0) AS '오감 (회)'
    FROM Users u
    LEFT JOIN Daily_Logs d 
        ON u.user_id = d.user_id 
        AND d.log_date BETWEEN ? AND ?
    GROUP BY u.user_id, u.name
"""

df_stats = pd.read_sql_query(query, conn, params=(start_of_week, end_of_week))

df_stats.index = df_stats.index + 1

if df_stats.empty:
    st.info("아직 등록된 DNA원이 없습니다.")
else:
    df_stats[['새벽기도 (회)', '일용할 양식 (회)', '오감 (회)']] = df_stats[['새벽기도 (회)', '일용할 양식 (회)', '오감 (회)']].astype(int)
    st.dataframe(df_stats, use_container_width=True)
    st.caption("💡 주일 모임에서 위 표를 띄워놓고 함께 한 주간의 은혜를 나눠보세요!")

# --- 4. 주간 기도제목 공유 영역 (추가됨) ---
st.divider()
st.header("🙏 이번 주 기도제목")

c = conn.cursor()
c.execute("SELECT content FROM Weekly_Prayer ORDER BY id DESC LIMIT 1")
latest_prayer = c.fetchone()

# 가장 최근 등록된 기도제목 출력 (글머리 기호 등 마크다운 자동 지원)
if latest_prayer and latest_prayer[0].strip():
    st.info(latest_prayer[0])
else:
    st.write("아직 등록된 기도제목이 없습니다.")

# 리더가 기도제목을 쉽게 바꿀 수 있는 입력 칸
with st.expander("⚙️ 리더 전용: 이번 주 기도제목 업데이트"):
    new_prayer = st.text_area("주일 소모임에서 나눈 기도제목을 입력하세요 (줄바꿈 가능)", height=150)
    if st.button("기도제목 업데이트"):
        if new_prayer:
            c.execute("INSERT INTO Weekly_Prayer (content) VALUES (?)", (new_prayer,))
            conn.commit()
            st.success("기도제목이 업데이트되었습니다! 🔄 새로고침(Cmd+R) 해주세요.")

conn.close()
