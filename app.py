import streamlit as st
import requests
from bs4 import BeautifulSoup as bs
import json
import time

botname = '봇이름'
call = '봇호출 문자'

class GraphQL:
    loadStory = """
    query SELECT_ENTRYSTORY(
        $pageParam: PageParam
        $query: String
        $user: String
        $category: String
        $term: String
        $prefix: String
        $progress: String
        $discussType: String
        $searchType: String
        $searchAfter: JSON
    ){
        discussList(
            pageParam: $pageParam
            query: $query
            user: $user
            category: $category
            term: $term
            prefix: $prefix
            progress: $progress
            discussType: $discussType
            searchType: $searchType
            searchAfter: $searchAfter
        ) {
            total
            list {
                id
                content
                created
                commentsLength
                likesLength
                user {
                    id
                    nickname
                    username
                }
            }
            searchAfter
        }
    }
    """

    login = """
    mutation (
        $username: String!, 
        $password: String!, 
        $rememberme: Boolean, 
        $captchaValue: String, 
        $captchaKey: String,
        $captchaType: String
    ) {
        signinByUsername (
            username: $username, 
            password: $password, 
            rememberme: $rememberme, 
            captchaValue: $captchaValue, 
            captchaKey: $captchaKey,
            captchaType: $captchaType
        ) {
            id
            username
            nickname
        }
    }
    """

    createComment = """
    mutation CREATE_COMMENT(
        $content: String
        $target: String
        $targetSubject: String
        $targetType: String
    ) {
        createComment(
            content: $content
            target: $target
            targetSubject: $targetSubject
            targetType: $targetType
        ) {
            comment {
                id
                content
                created
            }
        }
    }
    """

graphql = GraphQL()

def main():
    st.title(f'{botname} 컨트롤러')
    
    username = st.text_input('아이디', value='')
    password = st.text_input('암호', value='', type='password')
    
    if st.button(f'{botname} 실행'):
        with st.spinner('처리 중...'):
            with requests.Session() as s:
                st.write('로그인 중...')
                loginPage = s.get('https://playentry.org/signin')
                soup = bs(loginPage.text, 'html.parser')
                csrf = soup.find('meta', {'name': 'csrf-token'})
                login_headers = {'CSRF-Token': csrf['content'], 'Content-Type': 'application/json'}
                
                login_response = s.post('https://playentry.org/graphql',     
                    headers=login_headers, 
                    json={'query': graphql.login, 'variables': {'username': username, 'password': password, 'rememberme': False}}
                )
                
                login_data = login_response.json()
                if 'errors' in login_data:
                    st.error(f'로그인 실패: {login_data['errors'][0]['message']}')
                    return
                
                st.success('로그인 성공!')
                
                soup = bs(s.get('https://playentry.org').text, 'html.parser')
                xtoken = json.loads(soup.select_one('#__NEXT_DATA__').get_text())['props']['initialState']['common']['user']['xToken']
                headers = {
                    'X-Token': xtoken, 
                    'x-client-type': 'Client', 
                    'CSRF-Token': csrf['content'], 
                    'Content-Type': 'application/json'
                }
                
                st.write(f'{botname} 시작!')
                
                def create_comment(lid, ccontent):
                    s.post('https://playentry.org/graphql', 
                        headers=headers, 
                        json={'query': graphql.createComment, 
                                'variables': {'content': ccontent, 'target': lid, 'targetSubject': 'discuss', 'targetType': 'individual'}})
                pre_id = ''
                
                while True:
                    try:
                        req = s.post('https://playentry.org/graphql', 
                                    headers=headers, 
                                    json={'query': graphql.loadStory, 
                                    'variables': {
                                            'category': 'free',
                                            'searchType': 'scroll',
                                            'term': 'all',
                                            'discussType': 'entrystory',
                                            'pageParam': {'display': 1, 'sort': 'created'}
                                        }})
                        story_data = req.json()
                        
                        if 'data' in story_data and 'discussList' in story_data['data'] and 'list' in story_data['data']['discussList']:
                            story = story_data['data']['discussList']['list'][0]
                            llid = story['id']
                            content = story['content']
                            
                            if pre_id != llid:
                                if content.startswith(f'{call}'):
                                    command = content[len(call):]
                                    
                                    if command == botname:
                                        create_comment(llid, f'안녕하세요, {botname}입니다! 무엇을 도와드릴까요?')

                                    elif command == '내 정보' or command == '내정보':
                                        user_id = story['user']['id']
                                        try:
                                            response = requests.get(f'https://dut-api-atobe1108.vercel.app/profile/{user_id}')
                                            if response.status_code == 200:
                                                user_data = response.json()
                                                status = user_data['data']['userstatus']['status']
                                                following = status['following']
                                                follower = status['follower']
                                                qna = status['community']['qna']
                                                tips = status['community']['tips']
                                                free = status['community']['free']
                                                
                                                info_message = (f'팔로잉 수는 {following}명이며 팔로워 수는 {follower}명입니다. '
                                                                f'또한 묻고 답하기 개수는 {qna}개이며 작성한 노하우&팁 {tips}개이며 작성한 엔트리이야기 수는 {free}개입니다.')
                                                
                                                create_comment(llid, info_message)
                                            else:
                                                create_comment(llid, f'사용자 정보를 가져오는 데 실패했습니다. 상태 코드: {response.status_code}')
                                        except Exception as e:
                                            create_comment(llid, f'오류 발생: {str(e)}')
                                    else:
                                        create_comment(llid, f'"{command}" 명령어를 찾을 수 없습니다.')

                                    st.write(f'명령어 실행: {call}{command}')
                                    
                                    pre_id = llid
                        
                    except Exception as e:
                        st.error(f'오류 발생: {str(e)}')
                    
                    time.sleep(0.5)

if __name__ == '__main__':
    main()
