import os
import sys
import requests
import json
import pandas as pd


# noinspection NonAsciiCharacters,PyPep8Naming,SpellCheckingInspection
class KakaoAPI:
    """ 카카오톡 알림 발송 (별도 저장소 api-kakao 에서 가져온 모듈)

        · 접속키  xconfig/kakaoKey.json  (양식 kakaoKey.json.example)
        · 토큰    xapi/kakaoToken.json   (발송 때마다 갱신해서 덮어쓴다)
        · 원본의 서버-로컬 토큰 동기화는 뺐다 - 서버에 못 닿으면 발송까지 막혀서 (2026-09-14 주소 변경으로 전체 알림 중단) """

    def __init__(self):
        # 파일 위치 정의
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        self.path_접속키 = os.path.join(self.folder_프로젝트, 'xconfig', 'kakaoKey.json')
        self.path_토큰 = os.path.join(self.folder_베이스, 'kakaoToken.json')

        # 키 정의
        dic_접속키 = json.load(open(self.path_접속키, mode='rt', encoding='utf-8'))
        self.key_restapi = dic_접속키['key_restapi']
        self.key_admin = dic_접속키['key_radmin']

        # 토큰 정의
        self.dic_토큰 = json.load(open(self.path_토큰, mode='rt', encoding='utf-8'))

        # 로그 정의 - 로그 폴더는 xconfig/config.json 의 folder_log 를 따른다 (공개 저장소라 경로를 코드에 두지 않는다)
        s_머신 = 'mac' if sys.platform == 'darwin' else 'win' if sys.platform == 'win32' else None
        dic_config = json.load(open(os.path.join(self.folder_프로젝트, 'xconfig', 'config.json'), mode='rt', encoding='utf-8'))
        folder_log = dic_config['folder_log'][s_머신]
        self.path_log = os.path.join(folder_log, f'kakao_{pd.Timestamp.now().strftime('%Y%m%d')}.log')

    def make_log(self, s_text, li_loc=None):
        """ 입력 받은 s_text에 시간 붙여서 self.path_log에 저장 """
        # 정보 설정
        s_시각 = pd.Timestamp('now').strftime('%H:%M:%S')
        s_파일 = os.path.basename(sys.argv[0]).replace('.py', '')
        s_모듈 = sys._getframe(1).f_code.co_name

        # log 생성
        s_log = f'[{s_시각}] {s_파일} | {s_모듈} | {s_text}'

        # log 출력
        li_출력 = ['콘솔', '파일'] if li_loc is None else li_loc
        if '콘솔' in li_출력:
            print(s_log)
        if '파일' in li_출력:
            with open(self.path_log, mode='at', encoding='cp949') as file:
                file.write(f'{s_log}\n')

    def get_인가코드(self, s_리다이렉트주소):
        """ 브라우저를 통해 인가 코드 생성 (로그인 완료 후 나오는 주소창에서 코드 복사해서 _get_token 의 code에 입력)
            s_리다이렉트주소 - 카카오 개발자센터 앱에 등록한 리다이렉트 주소 """
        # url 정의
        url = 'https://kauth.kakao.com/oauth/authorize'

        # 요청쿼리 정의
        s_요청쿼리 = (f'{url}?'
                  f'client_id={self.key_restapi}&'
                  f'redirect_uri={s_리다이렉트주소}&'
                  f'response_type=code&'
                  f'scope=talk_message,profile,friends')

        # 서버 요청 (브라우저에서 열림)
        import webbrowser
        webbrowser.open(s_요청쿼리)

    def get_토큰발급(self, s_사용자, s_인가코드):
        """ 토큰 신규 발급 후 json 파일 저장 (인가코드는 1회만 사용 가능, 재실행 시 인가코드 다시 생성 필요) """
        # url 정의
        url = 'https://kauth.kakao.com/oauth/token'

        # 요청항목 정의
        dic_요청항목 = dict(grant_type='authorization_code',
                        client_id=self.key_restapi,
                        redirection_uri='https://localhost.com',
                        code=s_인가코드)

        # 서버 요청
        res = requests.post(url=url, data=dic_요청항목)
        dic_데이터 = res.json()

        # 데이터 정리
        self.dic_토큰[s_사용자] = dic_데이터
        json.dump(self.dic_토큰, open(self.path_토큰, mode='wt', encoding='utf-8'), indent=4, ensure_ascii=False)

    def get_토큰갱신(self):
        """ 저장된 refresh 토큰을 통해 access/refresh 토큰 갱신 후 저장 """
        # 사용자별 토큰 갱신
        for s_사용자 in self.dic_토큰.keys():
            # refresh 토큰 불러오기
            dic_토큰_사용자 = self.dic_토큰[s_사용자]
            s_토큰_refresh = dic_토큰_사용자['refresh_token']

            # url 정의
            url = 'https://kauth.kakao.com/oauth/token'

            # 요청항목 정의
            dic_요청항목 = dict(grant_type='refresh_token',
                            client_id=self.key_restapi,
                            refresh_token=s_토큰_refresh)

            # 서버 요청
            res = requests.post(url=url, data=dic_요청항목)
            dic_데이터 = res.json()

            # 갱신 실패 시 중단 - refresh 토큰 만료 등은 재시도로 풀리지 않는다 (get_인가코드 → get_토큰발급 으로 재발급)
            if 'error' in dic_데이터.keys():
                raise RuntimeError(f'카카오 토큰 갱신 실패 - {s_사용자} - '
                                   f'{dic_데이터.get("error")} {dic_데이터.get("error_description", "")}')

            # 데이터 정리 (access_token: 매번 갱신, refresh_token: 존재 시 갱신 - 1개월 미만)
            dic_토큰_사용자['access_token'] = dic_데이터['access_token']
            if 'refresh_token' in dic_데이터.keys():
                dic_토큰_사용자['refresh_token'] = dic_데이터['refresh_token']
            self.dic_토큰[s_사용자] = dic_토큰_사용자

        # 토큰 저장
        json.dump(self.dic_토큰, open(self.path_토큰, mode='wt', encoding='utf-8'), indent=2, ensure_ascii=False)

    def get_친구목록(self, s_사용자):
        """ 사용자에게 등록된 친구 목록 및 uuid 반환 (친구는 팀원에 추가 후 access token 을 발급 받은 후에 검색 가능) """
        # 토큰 불러오기
        dic_토큰_사용자 = self.dic_토큰[s_사용자]
        s_토큰_access = dic_토큰_사용자['access_token']

        # url 정의
        url = 'https://kapi.kakao.com/v1/api/talk/friends'

        # 요청항목 정의
        dic_헤더 = dict(Authorization=f'Bearer {s_토큰_access}')

        # 서버 요청
        res = requests.get(url=url, headers=dic_헤더)
        dic_데이터 = res.json()

        # 데이터 정리
        dic_친구목록_uuid = dict()
        for dic_친구목록 in dic_데이터['elements']:
            dic_친구목록_uuid[dic_친구목록['profile_nickname']] = dic_친구목록['uuid']

        return dic_친구목록_uuid

    def send_메세지(self, s_사용자, s_수신인, s_메세지, s_버튼이름='', s_연결url=''):
        """ 수신인에게 메세지 송부 """
        # 토큰 갱신
        self.get_토큰갱신()

        # 토큰 불러오기
        dic_토큰_사용자 = self.dic_토큰[s_사용자]
        s_토큰_access = dic_토큰_사용자['access_token']

        # 기준정보 정의
        dic_친구목록_uuid = self.get_친구목록(s_사용자=s_사용자)
        s_수신인_uuid = dic_친구목록_uuid[s_수신인]

        # url 정의
        url = 'https://kapi.kakao.com/v1/api/talk/friends/message/default/send'

        # 요청항목 정의
        dic_헤더 = dict(Authorization=f'Bearer {s_토큰_access}')
        dic_포스트 = dict(object_type='text',
                       text=s_메세지,
                       link={'web_url': s_연결url,
                             'mobile_web_url': s_연결url},
                       button_title=s_버튼이름)
        dic_요청항목 = dict(receiver_uuids=f'["{s_수신인_uuid}"]',
                        template_object=json.dumps(dic_포스트))

        # 서버 요청
        res = requests.post(url=url, headers=dic_헤더, data=dic_요청항목)

        # 데이터 정리
        s_전송결과 = '성공' if res.status_code == 200 else '실패'

        return s_전송결과

    def send_message(self, s_user, s_friend, s_text, s_button_title=None, s_url=None):
        """ 이전 코드 사용자를 위한 wrapper"""
        self.send_메세지(s_사용자=s_user, s_수신인=s_friend, s_메세지=s_text, s_버튼이름=s_button_title, s_연결url=s_url)


#######################################################################################################################
# noinspection SpellCheckingInspection
if __name__ == '__main__':
    k = KakaoAPI()

    # 초기 설정 (토큰 재발급이 필요할 때만)
    # k.get_인가코드(s_리다이렉트주소='카카오 앱에 등록한 리다이렉트 주소')
    # k.get_토큰발급(s_사용자='알림봇', s_인가코드='브라우저 주소창에서 복사한 인가코드')

    # 친구목록 조회
    # dic_친구목록_uuid = k.get_친구목록(s_사용자='알림봇')
