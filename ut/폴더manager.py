import os
import json

import ut.도구manager


# noinspection PyPep8Naming,NonAsciiCharacters,SpellCheckingInspection
def define_폴더정보():
    # config 읽어 오기
    folder_베이스 = os.path.dirname(os.path.abspath(__file__))
    folder_프로젝트 = os.path.dirname(folder_베이스)
    # dic_config = json.load(open(os.path.join(folder_프로젝트, 'config.json'), mode='rt', encoding='utf-8'))
    dic_config = ut.도구manager.config로딩()

    # 기준정보 생성
    dic_폴더정보 = dict()
    dic_폴더정보['folder_work'] = dic_config['folder_work']
    dic_폴더정보['folder_log'] = dic_config['folder_log']
    dic_폴더정보['folder_kakao'] = dic_config['folder_kakao']
    folder_work = dic_폴더정보['folder_work']

    # 매수매도 폴더 정의
    folder_매수매도 = os.path.join(folder_work, '매수매도')
    dic_폴더정보['매수매도'] = os.path.join(folder_매수매도)
    dic_폴더정보['매수매도|감시종목'] = os.path.join(folder_매수매도, '감시종목_sp')
    dic_폴더정보['매수매도|주문체결'] = os.path.join(folder_매수매도, '주문체결_ws')

    # 데이터 폴더 정의
    folder_데이터 = os.path.join(folder_work, '데이터')
    dic_폴더정보['데이터'] = os.path.join(folder_데이터)
    dic_폴더정보['데이터|차트수집'] = os.path.join(folder_데이터, '차트수집_tr')
    dic_폴더정보['데이터|주식체결'] = os.path.join(folder_데이터, '주식체결_ws')
    dic_폴더정보['데이터|전체종목'] = os.path.join(folder_데이터, '전체종목_tr')
    dic_폴더정보['데이터|조건검색'] = os.path.join(folder_데이터, '조건검색_ws')
    dic_폴더정보['데이터|대상종목'] = os.path.join(folder_데이터, '대상종목')
    dic_폴더정보['데이터|조회순위'] = os.path.join(folder_데이터, '조회순위_tr')
    dic_폴더정보['데이터|종목추천'] = os.path.join(folder_데이터, '종목추천')
    dic_폴더정보['데이터|종목관리'] = os.path.join(folder_데이터, '종목관리')
    dic_폴더정보['데이터|차트캐시'] = os.path.join(folder_데이터, '차트캐시')

    # 분석 폴더 정의
    folder_분석 = os.path.join(folder_work, '분석')
    dic_폴더정보['분석'] = os.path.join(folder_분석)
    dic_폴더정보['분석|백테스팅'] = os.path.join(folder_분석, '백테스팅')
    dic_폴더정보['분석|일봉분석'] = os.path.join(folder_분석, '일봉분석')






    # # work, run 폴더 정의
    # dic_폴더정보['work'] = folder_work
    # dic_폴더정보['run'] = os.path.join(folder_work, 'trader_run')
    #
    # # 이력 폴더 정의
    # folder_이력 = os.path.join(folder_work, 'trader_이력')
    # dic_폴더정보['이력'] = folder_이력
    # dic_폴더정보['이력|메세지'] = os.path.join(folder_이력, '메세지')
    # dic_폴더정보['이력|실시간'] = os.path.join(folder_이력, '실시간')
    # dic_폴더정보['이력|체결잔고'] = os.path.join(folder_이력, '체결잔고')
    # dic_폴더정보['이력|신호탐색'] = os.path.join(folder_이력, '신호탐색')
    # dic_폴더정보['이력|주문정보'] = os.path.join(folder_이력, '주문정보')
    # dic_폴더정보['이력|대상종목'] = os.path.join(folder_이력, '대상종목')
    # dic_폴더정보['이력|초봉정보'] = os.path.join(folder_이력, '초봉정보')
    # dic_폴더정보['이력|매개변수'] = os.path.join(folder_이력, '매개변수')
    #
    # # 데이터 폴더 정의
    # folder_데이터 = os.path.join(folder_work, 'collector_데이터')
    # dic_폴더정보['데이터'] = folder_데이터
    # dic_폴더정보['데이터|ohlcv'] = os.path.join(folder_데이터, 'ohlcv')
    # dic_폴더정보['데이터|캐시변환'] = os.path.join(folder_데이터, '캐시변환')
    # dic_폴더정보['데이터|정보수집'] = os.path.join(folder_데이터, '정보수집')
    # dic_폴더정보['데이터|전체종목'] = os.path.join(folder_데이터, '전체종목')
    # dic_폴더정보['데이터|분석대상'] = os.path.join(folder_데이터, '분석대상')
    # dic_폴더정보['데이터|체결정보'] = os.path.join(folder_데이터, '체결정보')
    #
    # # Transaction Flow 분석 폴더 정의
    # folder_TransactionFlow = os.path.join(folder_work, 'analyzer_TransactionFlow')
    # dic_폴더정보['tf분석'] = folder_TransactionFlow
    #
    # # 종목분석 폴더 정의
    # folder_종목분석 = os.path.join(folder_TransactionFlow, '종목분석')
    # dic_폴더정보['tf종목분석'] = folder_종목분석
    # dic_폴더정보['tf종목분석|일봉변동'] = os.path.join(folder_종목분석, '00_일봉변동')
    # dic_폴더정보['tf종목분석|지표생성'] = os.path.join(folder_종목분석, '10_지표생성')
    # dic_폴더정보['tf종목분석|분봉확인'] = os.path.join(folder_종목분석, '20_분봉확인')
    #
    # # 백테스팅 폴더 정의
    # folder_백테스팅 = os.path.join(folder_TransactionFlow, '백테스팅')
    # dic_폴더정보['tf백테스팅'] = folder_백테스팅
    # dic_폴더정보['tf백테스팅|매수매도'] = os.path.join(folder_백테스팅, '10_매수매도')
    # dic_폴더정보['tf백테스팅|결과정리'] = os.path.join(folder_백테스팅, '20_결과정리')
    # dic_폴더정보['tf백테스팅|결과요약'] = os.path.join(folder_백테스팅, '30_결과요약')
    # dic_폴더정보['tf백테스팅|수익요약'] = os.path.join(folder_백테스팅, '40_수익요약')
    # dic_폴더정보['tf백테스팅|매매이력'] = os.path.join(folder_백테스팅, '50_매매이력')

    return dic_폴더정보
