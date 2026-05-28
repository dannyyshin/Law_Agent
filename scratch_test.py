import os
import requests
import json

def test_search():
    LAW_OC = "eksldpf153"
    query = "민법"
    search_url = "https://www.law.go.kr/DRF/lawSearch.do"
    params = {"OC": LAW_OC, "target": "law", "type": "JSON", "query": query}
    res = requests.get(search_url, params=params)
    data = res.json()
    first_law = data.get('LawSearch', {}).get('law', [])[0]
    mst_id = first_law.get('법령일련번호')
    
    detail_url = "https://www.law.go.kr/DRF/lawService.do"
    detail_params = {"OC": LAW_OC, "target": "law", "type": "JSON", "MST": mst_id}
    d_res = requests.get(detail_url, params=detail_params)
    d_data = d_res.json()
    with open("scratch_law.json", "w", encoding="utf-8") as f:
        json.dump(d_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    test_search()
