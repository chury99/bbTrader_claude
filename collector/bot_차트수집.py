import os
import sys
import time

import pandas as pd
import re
import sqlite3

import ut


# 수집마감 시각 - 다음 날 08:58 실시간봇이 같은 키움 키로 조회·주문하므로 그 전에 손을 뗀다 (남은 건 다음 실행 때 이어받음)
S_수집마감 = '08:30:00'


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyAttributeOutsideInit
class CollectorBot:
    """ 장 마감 후 전체종목 일봉·분봉 수집 (spTraderV2 collector/bot_차트수집 에서 가져옴)

        · 코스피 업종일봉으로 개장일을 뽑고, db에 쌓인 마지막 일자 이후만 받는다
        · 종목마다 남은 일자를 한 번에 받아 일자별 임시 pkl 에 500종목마다 저장 → 중간에 끊겨도 이어서 받는다
        · 다 받으면 일봉은 연도별, 분봉은 월별 sqlite db 에 붙인다
        · spTraderV2 에서는 아침 bot_정보수집 이 만들던 전체종목 목록을 여기서 직접 받는다 """

    # noinspection PyUnresolvedReferences
    def __init__(self):
        # config 읽어 오기
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 로그 설정
        log = ut.로그maker.LogMaker(s_파일명=self.s_파일명, s_로그명='로그이름_collector')
        sys.stderr = ut.로그maker.StderrHook(path_에러로그=log.path_에러)
        self.make_로그 = log.make_로그

        # 폴더 정의
        dic_폴더정보 = ut.폴더manager.FolderManager().dic_폴더정보
        self.folder_차트수집 = dic_폴더정보['데이터|차트수집']
        self.folder_전체종목 = dic_폴더정보['데이터|전체종목']
        os.makedirs(self.folder_차트수집, exist_ok=True)
        os.makedirs(self.folder_전체종목, exist_ok=True)

        # 추가 폴더 정의
        self.folder_임시 = os.path.join(self.folder_차트수집, '임시저장')
        self.folder_일자 = os.path.join(self.folder_차트수집, '전체일자')
        self.folder_일봉 = os.path.join(self.folder_차트수집, '일봉')
        self.folder_분봉 = os.path.join(self.folder_차트수집, '분봉')
        os.makedirs(self.folder_임시, exist_ok=True)
        os.makedirs(self.folder_일자, exist_ok=True)
        os.makedirs(self.folder_일봉, exist_ok=True)
        os.makedirs(self.folder_분봉, exist_ok=True)

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.s_종료시각 = dic_config['종료시각']
        self.s_계좌번호 = str(dic_config['계좌번호'])
        dt_시작 = pd.Timestamp.now()
        self.dt_수집마감 = pd.Timestamp(f'{dt_시작:%Y-%m-%d} {S_수집마감}')
        self.dt_수집마감 = self.dt_수집마감 + pd.Timedelta(days=1) if self.dt_수집마감 <= dt_시작 else self.dt_수집마감

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()

        # 키움 API 연결
        sys.path.append(dic_config['folder_kiwoom'])
        import RestAPI_kiwoom
        self.api = RestAPI_kiwoom.RestAPIkiwoom(s_계좌번호=self.s_계좌번호)
        self.n_tr딜레이 = self.api.n_tr딜레이

        # 로그 기록
        self.make_로그(f'구동 시작')

    def get_전체종목(self):
        """ 코스피, 코스닥 전체 종목 조회하여 저장 (spTraderV2 bot_정보수집 에서 가져옴) """
        # 데이터 받아오기
        li_df_전체종목 = list()
        for s_시장 in ['코스피', '코스닥']:
            df_종목 = self.api.tr_업종별주가요청(s_시장=s_시장)
            df_종목['시장'] = s_시장
            li_df_전체종목.append(df_종목)

        # 데이터 정리
        df_전체종목 = pd.concat(li_df_전체종목, axis=0).sort_values('종목코드')
        df_전체종목 = df_전체종목.loc[:, ['종목코드', '종목명', '시장']].reset_index(drop=True)

        # 데이터 저장
        self.tool.df저장(df=df_전체종목, path=os.path.join(self.folder_전체종목, f'df_전체종목_{self.s_오늘}'))

        # 로그 기록
        df_코스피 = df_전체종목[df_전체종목['시장'] == '코스피']
        df_코스닥 = df_전체종목[df_전체종목['시장'] == '코스닥']
        self.make_로그(f'{self.s_오늘} 완료\n'
                     f' - {len(df_전체종목):,.0f} 종목 - 코스피 {len(df_코스피):,.0f}, 코스닥 {len(df_코스닥):,.0f}')

    def get_전체일자(self):
        """ 코스피 기준으로 시장이 열리는 일자를 찾아서 저장 """
        # 기준정보 정의
        dic_업종코드 = dict(코스피='001', 대형주='002', 중형주='003', 소형주='004', 코스닥='101',
                        KOSPI200='201', KOSTAR='302', KRX100='701')

        # 코스피 일봉 조회
        df_일봉 = self.api.tr_업종일봉조회요청(s_업종코드=dic_업종코드['코스피'])

        # 데이터 정리
        li_전체일자 = sorted(list(df_일봉['일자'].unique()))

        # 장 마감 전이면 당일 제외 - 장중 일부만 담긴 봉이 db에 들어가면 다음 수집 때 그날을 다시 받지 않는다
        if pd.Timestamp.now() < pd.Timestamp(self.s_종료시각):
            li_전체일자 = [일자 for 일자 in li_전체일자 if 일자 < self.s_오늘]

        # 데이터 저장
        pd.to_pickle(li_전체일자, os.path.join(self.folder_일자, f'li_전체일자_{self.s_오늘}.pkl'))

        # 로그 기록
        self.make_로그(f'저장 완료')

    def find_대상일자(self):
        """ db 파일에 저장된 데이터의 마지막 일자 확인 """
        # 최종일자 확인
        dic_최종일자 = dict(일봉=None, 분봉=None)
        for s_봉구분 in dic_최종일자.keys():
            # 최종파일 확인 - db 가 아직 없으면 최종일자 없음
            folder = self.folder_일봉 if s_봉구분 == '일봉' else self.folder_분봉 if s_봉구분 == '분봉' else None
            li_db파일 = [파일 for 파일 in os.listdir(folder) if '.db' in 파일]
            if len(li_db파일) == 0:
                continue
            s_최종파일명 = max(li_db파일)
            path_최종파일 = os.path.join(folder, s_최종파일명)

            # 테이블명 확인
            li_테이블명 = self.tool.sql불러오기(path=path_최종파일)
            s_테이블명_최종 = max(li_테이블명)

            # 최종일자 확인 - 일봉
            if s_봉구분 == '일봉':
                df_최종월 = self.tool.sql불러오기(path=path_최종파일, s_테이블명=s_테이블명_최종)
                dic_최종일자['일봉'] = df_최종월['일자'].max()

            # 최종일자 확인 - 분봉
            elif s_봉구분 == '분봉':
                dic_최종일자['분봉'] = re.findall(r'\d{8}', s_테이블명_최종)[0]

        # 전체일자 확인
        s_파일명 = max(파일 for 파일 in os.listdir(self.folder_일자) if '.pkl' in 파일)
        li_전체일자 = pd.read_pickle(os.path.join(self.folder_일자, s_파일명))

        # 대상일자 확인 - db 가 없으면 마지막 개장일 하루만 받는다
        dic_대상일자 = dict()
        for s_봉구분 in dic_최종일자.keys():
            dic_대상일자[s_봉구분] = [일자 for 일자 in li_전체일자 if 일자 > dic_최종일자[s_봉구분]]\
                                    if dic_최종일자[s_봉구분] is not None else li_전체일자[-1:]

        # 대상일자 등록
        self.dic_li대상일자 = dic_대상일자

        # 로그 기록
        self.make_로그(f'일봉-{dic_대상일자["일봉"]}, 분봉-{dic_대상일자["분봉"]}')

    def _load_전체종목(self, s_대상일자):
        """ 대상일자의 전체종목 목록 - 그날 파일이 없으면 그 뒤 가장 가까운 날 목록으로 대신한다
            (목록은 조회 시점 것만 받을 수 있다. 뒤 목록은 그 사이 상장폐지 종목이 빠지고, 신규상장은 데이터가 없어 제외로 걸러진다) """
        # 보유 목록 확인
        li_일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(self.folder_전체종목)
                       if 'df_전체종목' in 파일 and '.pkl' in 파일)
        li_이후일자 = [일자 for 일자 in li_일자 if 일자 >= s_대상일자]
        s_사용일자 = li_이후일자[0] if len(li_이후일자) > 0 else li_일자[-1]

        # 대체 사용 시 로그 기록
        if s_사용일자 != s_대상일자:
            self.make_로그(f'{s_대상일자} 전체종목 파일 없음 - {s_사용일자} 목록으로 대신')

        return pd.read_pickle(os.path.join(self.folder_전체종목, f'df_전체종목_{s_사용일자}.pkl'))

    def get_차트데이터(self, s_봉구분=None):
        """ 전체 종목 대상으로 일봉, 분봉 데이터 조회하여 일자별 pkl 파일로 저장 - 끝까지 받았으면 True

            원본은 일자마다 전 종목을 다시 조회했다. 분봉 조회는 항상 현재부터 거꾸로 넘겨받아서, 밀린 날이 많으면
            같은 구간을 일자 수만큼 반복해 받는다 (12일 밀림 기준 종목당 약 12초 → 전 종목 14시간).
            그래서 종목마다 남은 일자 전체를 한 번에 받아 일자별로 나눠 담는다 (종목당 약 1.5초).
            수집마감 시각을 넘기면 받은 데까지 저장하고 멈춘다 - 다음 실행 때 이어서 받는다. """
        # 기준정보 설정
        li_봉구분 = ['일봉', '분봉'] if s_봉구분 is None else [s_봉구분]

        # 차트 데이터 수집
        for s_봉구분 in li_봉구분:
            # 대상일자 확인
            li_대상일자 = self.dic_li대상일자[s_봉구분]
            if len(li_대상일자) == 0:
                continue

            # 일자별 진행현황 불러오기 - 받은 차트는 메모리에 두지 않고 종목코드만 확인
            dic_일자별 = dict()
            for s_대상일자 in li_대상일자:
                path_차트정보 = os.path.join(self.folder_임시, f'dic_차트정보_{s_봉구분}_{s_대상일자}.pkl')
                dic_차트정보 = pd.read_pickle(path_차트정보) if os.path.exists(path_차트정보)\
                                else dict(li_전체종목=list(), li_제외종목=list(), df_차트=pd.DataFrame())
                df_전체종목 = self._load_전체종목(s_대상일자=s_대상일자)
                df_차트 = dic_차트정보['df_차트']
                li_수집종목 = df_차트['종목코드'].unique().tolist() if len(df_차트) > 0 else list()
                dic_일자별[s_대상일자] = dict(path=path_차트정보,
                                          li_전체종목=df_전체종목['종목코드'].to_list(),
                                          li_제외종목=dic_차트정보['li_제외종목'],
                                          dic_코드2종목명=df_전체종목.set_index('종목코드')['종목명'].to_dict(),
                                          set_완료=set(li_수집종목) | set(dic_차트정보['li_제외종목']),
                                          li_df차트=list(), b_변경=False)
                del dic_차트정보, df_차트

            # 종목별 남은 일자 확인
            li_전체종목 = sorted(set(종목 for dic in dic_일자별.values() for 종목 in dic['li_전체종목']))
            dic_잔여일자 = {종목: [일자 for 일자, dic in dic_일자별.items()
                               if 종목 in dic['dic_코드2종목명'] and 종목 not in dic['set_완료']] for 종목 in li_전체종목}
            li_잔여종목 = [종목 for 종목 in li_전체종목 if len(dic_잔여일자[종목]) > 0]
            n_전체 = len(li_전체종목)
            n_기완료 = n_전체 - len(li_잔여종목)
            s_구간 = f'{li_대상일자[0]}~{li_대상일자[-1]}' if len(li_대상일자) > 1 else li_대상일자[0]
            self.make_로그(f'{s_봉구분}-{s_구간} ({len(li_대상일자)}일) - 남은 종목 {len(li_잔여종목):,.0f}/{n_전체:,.0f}')

            # 차트데이터 받아오기
            for i, s_종목코드 in enumerate(li_잔여종목):
                # 수집마감 확인 - 넘기면 받은 데까지 저장하고 멈춤
                if pd.Timestamp.now() >= self.dt_수집마감:
                    self._save_차트정보(dic_일자별=dic_일자별)
                    self.make_로그(f'수집마감 {self.dt_수집마감:%m-%d %H:%M} 도달 - {s_봉구분} {n_기완료 + i:,.0f}/{n_전체:,.0f}에서 멈춤, 다음 실행 때 이어받음')
                    return False

                # tr 조회 - 남은 일자 전체를 한 번에 (일시 오류는 쉬었다가 다시 시도)
                li_일자 = dic_잔여일자[s_종목코드]
                df_차트_종목별 = self._조회_재시도(s_봉구분=s_봉구분, s_종목코드=s_종목코드, s_시작일자=li_일자[0], s_종료일자=li_일자[-1])

                # tr 후 딜레이
                time.sleep(self.n_tr딜레이)

                # 일자별로 나눠 담기 - 데이터 있으면 수집, 없으면 제외종목 등록
                for s_일자 in li_일자:
                    dic = dic_일자별[s_일자]
                    df_일자 = df_차트_종목별[df_차트_종목별['일자'] == s_일자].copy() if len(df_차트_종목별) > 0 else pd.DataFrame()
                    if len(df_일자) > 0:
                        df_일자['종목명'] = dic['dic_코드2종목명'][s_종목코드]
                        dic['li_df차트'].append(df_일자)
                    else:
                        dic['li_제외종목'].append(s_종목코드)
                    dic['b_변경'] = True

                # 500종목마다, 그리고 마지막에 저장
                if i % 500 == 0 or i == len(li_잔여종목) - 1:
                    self._save_차트정보(dic_일자별=dic_일자별)

                    # 로그 기록
                    n_완료 = n_기완료 + i + 1
                    self.make_로그(f'{s_봉구분}-{s_구간}\n'
                                 f'  {n_완료 / n_전체 * 100:.2f}%-{n_완료:,.0f}/{n_전체:,.0f}-{s_종목코드}-{dic_일자별[li_일자[-1]]["dic_코드2종목명"][s_종목코드]}')

        return True

    def _조회_재시도(self, s_봉구분, s_종목코드, s_시작일자, s_종료일자):
        """ 차트 tr 조회 - 실패하면 1·2·4·8초 쉬고 다시 시도, 다섯 번 모두 실패하면 예외를 올린다
            (같은 키움 키를 다른 모듈이 함께 쓰면 호출 제한 응답이 json 이 아니게 와서 한 번씩 깨진다 - 2026-09-14 확인) """
        for n_시도 in range(5):
            try:
                if s_봉구분 == '일봉':
                    return self.api.tr_주식일봉차트조회요청(s_종목코드=s_종목코드, s_시작일자=s_시작일자, s_종료일자=s_종료일자)
                if s_봉구분 == '분봉':
                    return self.api.tr_주식분봉차트조회요청(s_종목코드=s_종목코드, s_시작일자=s_시작일자, s_종료일자=s_종료일자, s_틱범위='1')
                return pd.DataFrame()
            except Exception as e:
                if n_시도 == 4:
                    raise
                self.make_로그(f'!!! {s_봉구분} 조회 실패 {n_시도 + 1}회 - {s_종목코드} - {type(e).__name__}, {2 ** n_시도}초 후 재시도')
                time.sleep(2 ** n_시도)

    @staticmethod
    def _save_차트정보(dic_일자별):
        """ 일자별로 모아둔 차트를 임시 pkl 에 붙여 저장하고 메모리에서 비운다 """
        for dic in dic_일자별.values():
            # 변경 없으면 통과
            if not dic['b_변경']:
                continue

            # 기존 저장분 불러오기
            dic_차트정보 = pd.read_pickle(dic['path']) if os.path.exists(dic['path']) else dict(df_차트=pd.DataFrame())
            dic_차트정보['li_전체종목'] = dic['li_전체종목']
            dic_차트정보['li_제외종목'] = dic['li_제외종목']

            # 새로 받은 데이터 병합
            if len(dic['li_df차트']) > 0:
                df_차트 = pd.concat(dic['li_df차트'], axis=0)
                li_컬럼명_앞 = ['일자', '종목코드', '종목명']
                li_컬럼명 = li_컬럼명_앞 + [컬럼 for 컬럼 in df_차트.columns if 컬럼 not in li_컬럼명_앞]
                df_병합 = pd.concat([dic_차트정보['df_차트'], df_차트[li_컬럼명]], axis=0).drop_duplicates()
                dic_차트정보['df_차트'] = df_병합.sort_values('종목코드').reset_index(drop=True)

            # 데이터 저장
            pd.to_pickle(dic_차트정보, dic['path'])
            dic['li_df차트'] = list()
            dic['b_변경'] = False

    def update_db파일(self):
        """ 임시저장된 pkl 파일 읽어서 db 파일로 저장 """
        # 대상파일 확인
        li_대상파일 = sorted(파일 for 파일 in os.listdir(self.folder_임시) if 'dic_차트정보' in 파일 and '.pkl' in 파일)

        # db파일 업데이트
        for s_파일명 in li_대상파일:
            # 기준정보 정의
            dic_차트정보 = pd.read_pickle(os.path.join(self.folder_임시, s_파일명))
            s_봉구분 = re.findall(r'.봉', s_파일명)[0]
            s_일자 = re.findall(r'\d{8}', s_파일명)[0]
            df_차트 = dic_차트정보['df_차트']
            li_전체종목 = dic_차트정보['li_전체종목']
            li_제외종목 = dic_차트정보['li_제외종목']
            li_수집종목 = df_차트['종목코드'].unique().tolist()

            # 신뢰성 검사 - 미충족 시 진행 종료
            if len(li_전체종목) != len(li_수집종목) + len(li_제외종목):
                # 로그 기록
                self.make_로그(f'신뢰성 이상\n'
                             f'- 전체 {len(li_전체종목):,.0f} - 수집 {len(li_수집종목):,.0f} - 제외 {len(li_제외종목):,.0f}')
                raise AttributeError('신뢰성 이상')

            # 데이터 검사
            if len(li_수집종목) < len(li_전체종목) * 0.7:
                # 로그 기록
                self.make_로그(f'수집종목 수 이상\n'
                             f'- 전체 {len(li_전체종목):,.0f} - 수집 {len(li_수집종목):,.0f} - 제외 {len(li_제외종목):,.0f}')
                raise AttributeError('수집종목 수 이상')

            # 데이터 정리
            df_차트 = df_차트[df_차트['시간'] <= '15:30:00'] if s_봉구분 == '분봉' else df_차트

            # db 정의
            path = os.path.join(self.folder_일봉, f'ohlcv_일봉_{s_일자[:4]}.db') if s_봉구분 == '일봉' else \
                os.path.join(self.folder_분봉, f'ohlcv_분봉_{s_일자[:4]}_{s_일자[4:6]}.db') if s_봉구분 == '분봉' else None
            s_테이블명 = f'ohlcv_일봉_{s_일자[:6]}' if s_봉구분 == '일봉' else \
                f'ohlcv_분봉_{s_일자}' if s_봉구분 == '분봉' else None

            # db 불러오기
            li_테이블명 = self.tool.sql불러오기(path=path)
            df_기존 = self.tool.sql불러오기(path=path, s_테이블명=s_테이블명) if s_테이블명 in li_테이블명 else pd.DataFrame()

            # db 업데이트
            li_정렬키 = ['일자', '종목코드'] if s_봉구분 == '일봉' else ['일자', '종목코드', '시간'] if s_봉구분 == '분봉' else None
            df_신규 = pd.concat([df_기존, df_차트], axis=0).drop_duplicates().sort_values(li_정렬키).reset_index(drop=True)

            # db 저장
            con = sqlite3.connect(path)
            df_신규.to_sql(name=s_테이블명, con=con, index=False, if_exists='replace')
            con.close()

            # 임시파일 삭제
            os.remove(os.path.join(self.folder_임시, s_파일명))

            # 로그 기록
            self.make_로그(f'{s_봉구분}-{s_일자}')


def run():
    """ 실행 함수 """
    c = CollectorBot()
    c.get_전체종목()
    c.get_전체일자()
    c.find_대상일자()
    b_완료 = c.get_차트데이터()
    if b_완료:
        c.update_db파일()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
