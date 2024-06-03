import requests
from bs4 import BeautifulSoup
from functools import wraps
from selenium import webdriver
import pandas as pd
import re
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

import re

def extract_weights(text, price):
    # price 문자열에서 끝에 있는 '원'과 ',' 제거 후 실수형으로 변환
    price = price.replace(',', '').replace('~', '').rstrip('원')
    price = float(price)
    
    # 정규식 패턴 정의: 숫자 뒤에 선택적으로 공백이 있고 'kg' 또는 'g'가 오는 경우
    pattern = r'(\d+(?:\.\d+)?)\s*(kg|g)'
    
    # 정규식을 사용하여 일치하는 모든 패턴을 찾기
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    # per 변수 초기화
    per = 'coming soon'
    
    for match in matches:
        if match[1].lower() == 'kg':  # 대소문자 구분 없이 비교
            weight = float(match[0]) * 1000  # kg를 g로 변환
        elif match[1].lower() == 'g':
            weight = float(match[0])
        
        if weight == 0:
            return per  # weight가 0이면 'coming soon' 반환
        
        gramPrice = price / weight
        per = int(gramPrice * 100)  # 100g당 가격
    
    # 가격을 콤마로 구분하고 '원'을 추가하여 문자열로 변환
    per_price_str = f"{per:,}원" if isinstance(per, (int, float)) else per
    
    return per_price_str


# kurly page number 가져오기
def get_page_number(URL):
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')
    options.add_argument("disable-gpu")
    page_number = []

    # Selenium으로 웹 페이지 로드
    driver = webdriver.Chrome(options=options)
    driver.get(URL)
    html = driver.page_source

    soup = BeautifulSoup(html, "lxml")
    page_number = soup.find("div", class_=["css-rdz8z7", "e82lnfz1"]).find_all("a", class_=["css-19yo1fh", "e82lnfz0"])
    page_numbers = []
    for i in page_number:
        page_numbers.append(i.text)
    # 빈 문자열을 필터링하여 제거하고 정수로 변환
    page_numbers = [int(number) for number in page_numbers if number.strip()]
    max_page_number = max(page_numbers)
    return max_page_number

# 각 페이지의 상품 정보 크롤링
def getPageOfKurlyItems(Kurly_URL):
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')
    options.add_argument("disable-gpu")

    # Selenium으로 웹 페이지 로드
    driver = webdriver.Chrome(options=options)
    driver.get(Kurly_URL)

    # 스크롤 높이 확인
    last_height = driver.execute_script("return document.body.scrollHeight")
    # print(last_height)

    # 스크롤을 100픽셀씩 이동
    scroll_amount = 100
    # scroll_pause_time = 1
    cnt_scroll = 0

    # print(last_height / scroll_amount)

    while True:
        cnt_scroll += 1
        print(cnt_scroll)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        # sleep(scroll_pause_time) 
        driver.execute_script(f"window.scrollBy({scroll_amount * (cnt_scroll -1)}, {scroll_amount * cnt_scroll});")
        if scroll_amount * cnt_scroll >= (int)(last_height):
            break

    items = driver.find_elements(By.CSS_SELECTOR, ".css-8bebpy.e1c07x488")
    button = driver.find_elements(By.CSS_SELECTOR, ".css-13xu5fn.e17x72af0")

    newItem = []
    newItem_data = []
    for btn, item in zip(button, items):
        title = item.find_element(By.CSS_SELECTOR, ".css-1dry2r1.e1c07x485").text
        site = "마켓컬리"
        # catagory = "."
        # production = "."
        img = item.find_elements(By.CSS_SELECTOR, ".css-1zjvv7")
        src = img[0].get_attribute('src')
        imgLink = src if src and not src.startswith('data:image') else 0
        itemLink = item.get_attribute('href')
        if not itemLink.startswith("https"):
            itemLink = itemLink.replace("kurly.com", "")
        price = item.find_element(By.CSS_SELECTOR,".sales-price.css-18tpqqq.ei5rudb1").text
        weightPerUnit = extract_weights(title, price)

        try:
            element_percent = item.find_element(By.CSS_SELECTOR, ".css-19lkxd2.ei5rudb0")
            percent = element_percent.text
        except NoSuchElementException:
            percent = "0%"

        try:
            element_realPrice = item.find_element(By.CSS_SELECTOR, ".dimmed-price.css-18tpqqq.ei5rudb1")
            realPrice = element_realPrice.text
        except NoSuchElementException:
            realPrice = price

        if btn.text.strip() != "재입고 알림":   
            newItem_data = {
                "name" : title,
                "site" : site,
                "img" : imgLink,
                "url" : itemLink,
                "price" : price,
                "discount" : percent,
                "preprice" : realPrice,
                "perprice" : weightPerUnit,
            }
            if newItem_data["perprice"] != 'coming soon':
                newItem.append(newItem_data)
        
    driver.quit()
    return newItem

# 모든 상품 정보 모으기
def get_allKurlyItems(pageNum, URL):
    allItems = []
    partOfItems = []
    for i in range(pageNum):
        partOfItems = getPageOfKurlyItems(f"{URL}?page={i + 1}")
        allItems.extend(partOfItems)
    return allItems

# 필터링하기
def myKurlyItems(allItems):
    finalItemList = []
    df = pd.read_excel('keyword.xlsx')
    keyword_list = df["카테고리"].to_list()
    for item in allItems:
        for keyword in keyword_list:
            if keyword in item["name"] and "재배" not in item["name"]:
                category = df[df["카테고리"].str.contains(keyword, case=False, na=False)].values.tolist()
                for cat in category:
                    newItem = item.copy()  # 항목을 복사하여 각각 다른 카테고리로 저장
                    newItem["category"] = cat[1]
                    newItem["incategory"] = cat[0]
                    finalItemList.append(newItem)

    return finalItemList

# 실행 함수
def kurly_crawling(URL):
    allItems = []
    pageNum = get_page_number(URL)
    allItems = get_allKurlyItems(pageNum, URL)
    finalItems = myKurlyItems(allItems)
    return finalItems

# Coupang 크롤링 함수
def C_get_partItems(URL):
    print(f"Scrapping {URL}........\n")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3"}
    response = requests.get(URL, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    items = []
    for page in soup.find_all("li", class_=["baby-product", "renew-badge"]):
        title = page.find("dd", class_="descriptions").find("div", class_="name").text.strip()
        site = "쿠팡"
        imgLink = page.find("img").get('src')
        itemLink = page.find("a", class_="baby-product-link").get('href')
        price = page.find("strong", class_="price-value").text.strip()

        percent = page.find("span", class_="discount-percentage")

        realPrice = page.find("del", class_="base-price")
        realPrice_num = None
        if realPrice:
            realPrice_nums = re.findall(r'\d+', realPrice.text)
            realPrice_num = ''.join(realPrice_nums)

        pricePerGram = page.find("span", class_="unit-price")
        em = []
        if pricePerGram:
            em = pricePerGram.find_all("em")
        else:
            ver2_pricePerGram = extract_weights(title, price)

        # 상품 주소와 이미지 주소에 각각 "https://www." 및 "https://" 추가
        item_data = {
            "name": title,
            "site": site,
            "ime": f"https:{imgLink}" if imgLink.startswith("//") else imgLink,
            "url": f"https://www.coupang.com{itemLink}",
            "price": price,
            "discount": percent.text if percent else "0%",
            "preprice": realPrice_num if realPrice else price,
            "perprice": em[1].text if pricePerGram else ver2_pricePerGram,
        }
        if item_data["perprice"] != 'coming soon':
            items.append(item_data)
    return items

# 카테고리의 아이템 가져오기
def C_get_CategoryItems(URL, keyword):
    count = 1
    allCategoryItems = []
    finalCategoryItems = []
    df = pd.read_excel('keyword.xlsx')
    while True:
        partItems = []
        partItems = C_get_partItems(f"{URL}?page={count}")
        if not partItems:
            break
        else:
            allCategoryItems.extend(partItems)
            count += 1
    
    for Item in allCategoryItems:
        if keyword in Item["name"] and "재배" not in Item["name"] and "배송" not in Item["name"]:
            category = df[df["카테고리"].str.contains(keyword, case=False, na=False)].values.tolist()
            Item["category"] = category[0][1]
            Item["incategory"] = category[0][0]
            finalCategoryItems.append(Item)

    # print(len(finalCategoryItems))
    return finalCategoryItems

# 모든 카테고리 상품 정보 모으기
def coupang_crawling(URL):
    df = pd.read_excel('keyword.xlsx')
    keywordList = df["카테고리"].tolist()
    allItems = []
    for keyword in keywordList:
        keyword_values = df[df["카테고리"] == keyword].values.tolist()
        linkValue = keyword_values[0][2]
        categoryItems = []
        categoryItems = C_get_CategoryItems(f"{URL}/{linkValue}", keyword)
        allItems.extend(categoryItems)

    return allItems

# 인덱스를 재설정하여 번호 부여하는 함수 정의
def reset_and_assign_id(df):
    df = df.reset_index(drop=True).reset_index().rename(columns={'index': 'id'})
    df['id'] = df['id'] + 1  # 번호를 1부터 시작하도록 조정
    return df

# main
kruly_URL = "https://www.kurly.com/categories/908"
coupang_URL = "https://www.coupang.com/np/categories"
kurlyItmes = []
coupangItems = []
keyList = ["name", "site", "category", "incategory", "img", "url", "price", "discount", "preprice", "perprice"]
kurlyItems = kurly_crawling(kruly_URL)
coupangItems = coupang_crawling(coupang_URL)
allItems = kurlyItems + coupangItems
print(len(allItems))

df = pd.DataFrame(allItems, columns=keyList)

# 카테고리에 따라 필터링
domestic_fruits = df[df["category"].str.contains("국내", na=False)]
foreign_fruits = df[df["category"].str.contains("외국", na=False)]
frozen_fruits = df[df["category"].str.contains("냉동", na=False)]

delete_domestic_keywords = ['칠레', '미국', '페루', '그리스', '터키', '이집트', '중국', '캐나다', '일본', '남미', '호주', '수입', '항공', '캘리포니아', '워싱턴', '닝샤', '알파인레드', '장백산', '엘라그산', '플라스틱', '따기', '냉동', '착즙기', '압착기', '홀로그램', '포장박스', '리필캔', '씨앗']
mask = domestic_fruits.apply(lambda x: x.str.contains('|'.join(delete_domestic_keywords))).any(axis=1)
final_domestic_fruits = domestic_fruits[~mask]

delete_foreign_keywords = ['냉동', '착즙기', '압착기', '플라스틱', '씨앗']
mask2 = foreign_fruits.apply(lambda x: x.str.contains('|'.join(delete_foreign_keywords))).any(axis=1)
final_foreign_fruits = foreign_fruits[~mask2]

final_domestic_fruits = reset_and_assign_id(final_domestic_fruits)
final_foreign_fruits = reset_and_assign_id(final_foreign_fruits)
frozen_fruits = reset_and_assign_id(frozen_fruits)

# 엑셀 파일로 저장
df.to_excel('All Fruit Data.xlsx', index=False)
final_domestic_fruits.to_excel('Domestic Fruit Data.xlsx', index=False)
final_foreign_fruits.to_excel('Foreign Fruit Data.xlsx', index=False)
frozen_fruits.to_excel('Frozen Fruit Data.xlsx', index=False)

print("All Fruit Data 파일이 성공적으로 생성되었습니다.")
print("Domestic, Foreign, Frozen Fruit Data 파일이 성공적으로 생성되었습니다.")