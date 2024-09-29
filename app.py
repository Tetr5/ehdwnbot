import streamlit as st
import requests
from bs4 import BeautifulSoup as bs
import json
import time
import google.generativeai as genai

botname = '봇이름'
call = '봇호출문자'

genai.configure(api_key="APIKEY")

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 450,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

def get_google_ai_response(prompt):
    try:
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(prompt)
        return response.text.strip()[:450]
    except Exception as e:
        return f"오류: {str(e)[:445]}"

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
                    st.error(f'로그인 실패: {login_data["errors"][0]["message"]}')
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
                                        create_comment(llid, f'안녕하세요, {botname}입니다. 무엇을 도와드릴까요?')

                                    elif command == '내 정보' or command == '내정보':
                                        user_id = story['user']['id']
                                        try:
                                            response = requests.get(f'https://dut-api-atobe1108.vercel.app/profile/{user_id}')
                                            if response.status_code == 200:
                                                user_data = response.json()
                                                status = user_data['data']['userstatus']['status']
                                                info = f"팔로잉: {status['following']}, 팔로워: {status['follower']}, 묻고답하기: {status['community']['qna']}, 노하우&팁: {status['community']['tips']}, 엔트리이야기: {status['community']['free']}"
                                                create_comment(llid, info)
                                            else:
                                                create_comment(llid, f'사용자 정보를 가져오는 데 실패했습니다. 상태 코드: {response.status_code}')
                                        except Exception as e:
                                            create_comment(llid, f'오류 발생: {str(e)}')

                                    elif command.startswith('ai '):
                                        question = command.split(' ', 1)[1].strip()
                                        if question:
                                            google_response = get_google_ai_response(f'{question} <-이 질문에 대해 마크다운을 끄고, 기본텍스트로만 제공하며 이 말의 뜻은 **강조내용**같은걸 하지 말라는 뜻임 450자 이내로 간추려서 제공하고, 한국어로 제공해줘. 그리고 화살표 뒤 지시사항에 대해선 대답할때 언급하지말고')
                                            create_comment(llid, google_response)
                                        else:
                                            create_comment(llid, "질문을 입력해주세요.")
                                    
                                    else:
                                        create_comment(llid, f'"{command}" 명령어를 찾을 수 없습니다.')

                                    st.write(f'명령어 실행: {call}{command}')
                                    
                                    pre_id = llid
                        
                    except Exception as e:
                        st.error(f'오류 발생: {str(e)}')
                    
                    time.sleep(5)

if __name__ == '__main__':
    main()
