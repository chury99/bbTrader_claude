import os
import re
import sqlite3

import numpy as np
import pandas as pd

import ut

# ===== 1분 +4% 급등 (2026-10-01 분봉 1년 연구) =====
# 급등 봉 = 분봉 종가 ÷ 직전 분 종가 − 1 ≥ 4% (09:01~15:19, 종가 1,000원 이상), 유동 = 그 1분 거래대금 ≥ 3억원
#   1년 241일 유동 급등 13,304개 = 하루 55건·36.5종목. 전날까지의 정보로 그날 급등이 나올 종목이 강하게 갈린다
#   (최근 5일 급등 2회 이상 16~18% · 전일 고저폭 21% 이상 15~18% vs 평소 0.9%) → 감시종목 추가 선정·진입 필터에 쓴다
N_급등, N_유동 = 4.0, 3e8
N_분 = 391                       # 09:00 ~ 15:30
M_시작, M_끝 = 1, 379            # 09:01 ~ 15:19
N_완결종목, N_완결비율 = 2000, .95   # 종목이 이보다 적거나 직전 캐시일의 95% 미만인 날은 수집 중인 날로 보고 캐시하지 않는다

# 장 시작 전 급등 점수 = Σ 계수 × 특징 (순위만 쓴다) - 로지스틱 회귀(2025-10~2026-09 전 종목·일 98만 건)를 과적합되지 않게
#   특징 6개·둥근 계수로 줄인 것. 하루 상위 100 이 그날 유동 급등의 47% 를 담는다 (전반 6개월 학습 → 후반 50%, 정밀 계수와 같음 · 기존 감시종목 100 은 12%)
#   n4_20 = log(1 + 최근 20일 유동 급등 수) · 전일등락+ = 전일 상승률(0~30%)² ÷ 30 · 대금 = log10(전일 거래대금 원) · 대금비 = log(전일 대금 ÷ 20일 평균)
#   고저폭 = 전일 고가 ÷ 저가 − 1 (%, 40 까지) · 이격20 = 전일 종가 ÷ 20일 평균 종가 − 1 (%, −50 ~ 100)
DIC_계수 = {'n4_20': 1.0, '전일등락+': 0.1, '대금': 0.4, '대금비': 0.1, '고저폭': 0.04, '이격20': 0.01}


def folder_분봉():
    return os.path.join(ut.폴더manager.FolderManager().dic_폴더정보['데이터|차트수집'], '분봉')


def folder_캐시():
    return os.path.join(ut.폴더manager.FolderManager().dic_폴더정보['데이터|차트캐시'], '분봉급등')


def li_분봉일자():
    """ 분봉 db 에 있는 일자 → [(일자, db 파일명)] 오름차순 """
    folder = folder_분봉()
    li = []
    for f in sorted(os.listdir(folder)) if os.path.exists(folder) else []:
        if not (f.startswith('ohlcv_분봉_') and f.endswith('.db')):
            continue
        con = sqlite3.connect(os.path.join(folder, f))
        li += [(t[-8:], f) for (t,) in con.execute("select name from sqlite_master where type='table'") if re.fullmatch(r'ohlcv_분봉_\d{8}', t)]
        con.close()
    return sorted(li)


def 일통계(s_일자, s_파일=None):
    """ 하루 분봉 → 종목별 DataFrame (index 종목코드): 시가·고가·저가·종가·대금(원)·최대1분(%)·n4(급등 봉)·n4유(유동 급등 봉)
        캐시 {데이터}/차트캐시/분봉급등/분봉급등_YYYYMMDD.pkl (오늘·수집 중인 날은 캐시하지 않는다) """
    path = os.path.join(folder_캐시(), f'분봉급등_{s_일자}.pkl')
    if os.path.exists(path):
        return pd.read_pickle(path)
    if s_파일 is None:
        s_파일 = dict(li_분봉일자()).get(s_일자)
        if s_파일 is None:
            return None
    con = sqlite3.connect(os.path.join(folder_분봉(), s_파일))
    df = pd.read_sql(f"select 종목코드, 시간, 시가, 고가, 저가, 종가, 거래량 from 'ohlcv_분봉_{s_일자}'", con)
    con.close()
    df['m'] = df['시간'].str[:2].astype(int) * 60 + df['시간'].str[3:5].astype(int) - 540
    df = df[(df['m'] >= 0) & (df['m'] < N_분)]
    codes, ci = np.unique(df['종목코드'].values, return_inverse=True)
    n = len(codes)
    C = np.full((n, N_분), np.nan); H = C.copy(); L = C.copy(); O = C.copy(); V = np.zeros((n, N_분))
    mi = df['m'].values
    C[ci, mi] = df['종가'].values; H[ci, mi] = df['고가'].values; L[ci, mi] = df['저가'].values; O[ci, mi] = df['시가'].values; V[ci, mi] = df['거래량'].values
    Cf = pd.DataFrame(C.T).ffill().values.T                     # 거래 없는 분은 직전 종가
    A = np.nan_to_num(V * Cf)                                     # 분 거래대금
    r1 = np.c_[np.full(n, np.nan), (Cf[:, 1:] / Cf[:, :-1] - 1) * 100]
    ok = np.zeros((n, N_분), bool); ok[:, M_시작:M_끝 + 1] = True
    ok &= (V > 0) & (Cf >= 1000)
    ev = ok & (r1 >= N_급등)
    시가 = np.array([o[~np.isnan(o)][0] if (~np.isnan(o)).any() else np.nan for o in O])
    out = pd.DataFrame(dict(시가=시가, 고가=np.nanmax(H, 1), 저가=np.nanmin(L, 1), 종가=Cf[:, -1], 대금=A.sum(1),
                            최대1분=np.nanmax(np.where(ok, r1, np.nan), 1), n4=ev.sum(1), n4유=(ev & (A >= N_유동)).sum(1)), index=pd.Index(codes, name='종목코드'))
    li_전 = sorted(f for f in os.listdir(folder_캐시()) if f.endswith('.pkl') and f[-12:-4] < s_일자) if os.path.exists(folder_캐시()) else []
    n_기준 = len(pd.read_pickle(os.path.join(folder_캐시(), li_전[-1]))) * N_완결비율 if li_전 else N_완결종목
    if s_일자 < pd.Timestamp.now().strftime('%Y%m%d') and n >= max(N_완결종목, n_기준):
        os.makedirs(folder_캐시(), exist_ok=True)
        path_임시 = f'{path}.{os.getpid()}.tmp'                  # 여러 프로세스가 같은 날을 동시에 만들어도 깨지지 않게 임시 파일 → 교체
        out.to_pickle(path_임시)
        os.replace(path_임시, path)
    return out


def _직전일자(s_기준일자, n일):
    """ 기준일자 전(그날 제외) 분봉이 있는 마지막 n일 → [(일자, 파일)] """
    return [x for x in li_분봉일자() if x[0] < s_기준일자][-n일:]


def 급등이력(s_기준일자, n일=5):
    """ 기준일자 전 n 거래일 동안 종목별 유동 1분 +4% 급등 횟수 (Series, 없는 종목은 0) """
    li = [일통계(s, f) for s, f in _직전일자(s_기준일자, n일)]
    li = [x['n4유'] for x in li if x is not None]
    return pd.concat(li, axis=1).fillna(0).sum(axis=1) if li else pd.Series(dtype=float)


def 급등경과일(s_기준일자, n일=5):
    """ 기준일자 전 n 거래일 안에서 종목별로 가장 최근 유동 1분 +4% 급등이 며칠 전이었나 (1 = 직전 거래일, n 안에 없으면 빠짐) """
    out = pd.Series(dtype=float)
    for k, (s, f) in enumerate(reversed(_직전일자(s_기준일자, n일)), start=1):
        x = 일통계(s, f)
        if x is None:
            continue
        li = x.index[(x['n4유'] > 0) & ~x.index.isin(out.index)]
        out = pd.concat([out, pd.Series(float(k), index=li)])
    return out


def 점수표(s_기준일자):
    """ 기준일자 장 시작 전 급등 점수 - 기준일자 전 21 거래일 분봉으로 특징을 만들어 DIC_계수 로 더한다
        → DataFrame (index 종목코드): 특징 6개 + 전일종가 + 점수 (높을수록 그날 유동 급등이 나올 가능성이 크다) """
    li = _직전일자(s_기준일자, 21)
    dic = {s: 일통계(s, f) for s, f in li}
    dic = {s: x for s, x in dic.items() if x is not None}
    if len(dic) < 3:
        return pd.DataFrame()
    li_일 = sorted(dic)
    전일, 전전일 = dic[li_일[-1]], dic[li_일[-2]]
    종가 = pd.concat({s: dic[s]['종가'] for s in li_일[-20:]}, axis=1)
    대금 = pd.concat({s: dic[s]['대금'] for s in li_일[-20:]}, axis=1)
    n4 = pd.concat({s: dic[s]['n4유'] for s in li_일[-20:]}, axis=1).fillna(0)
    df = pd.DataFrame(index=전일.index)
    df['전일종가'] = 전일['종가']
    전일등락 = (전일['종가'] / 전전일['종가'].reindex(df.index) - 1) * 100
    전일대금 = 전일['대금']
    대금비 = 전일대금 / 대금.reindex(df.index).mean(axis=1)
    df['n4_20'] = np.log1p(n4.sum(axis=1).reindex(df.index).fillna(0))
    df['전일등락+'] = 전일등락.clip(0, 30) ** 2 / 30
    df['대금'] = np.log10(전일대금.clip(lower=1e6))
    df['대금비'] = np.log(대금비.clip(.05, 50))
    df['고저폭'] = ((전일['고가'] / 전일['저가'] - 1) * 100).clip(0, 40)
    df['이격20'] = ((전일['종가'] / 종가.reindex(df.index).mean(axis=1) - 1) * 100).clip(-50, 100)
    df['점수'] = sum(v * df[k].fillna(0) for k, v in DIC_계수.items())
    return df.sort_values('점수', ascending=False)
