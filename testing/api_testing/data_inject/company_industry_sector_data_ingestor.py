import requests
import os

# API endpoint
API_URL = "http://localhost:8080/api/data_inject_graph_db/csv_structured_company_industry_sector_data"
#API_URL = "http://34.68.84.147:8080/api/data_inject_graph_db/csv_structured_company_industry_sector_data"


data = [
    ["C:/Users/ASUS/Documents/Get-Deep/data/KnowledgeGraphData/Strunctured/CompanyBELONG_TOIndustry.csv", "ci"],
    ["C:/Users/ASUS/Documents/Get-Deep/data/KnowledgeGraphData/Strunctured/CompanyCOMPETES_WITHCompany.csv", "cc"],
    ["C:/Users/ASUS/Documents/Get-Deep/data/KnowledgeGraphData/Strunctured/IndustryBELONG_TOSector.csv", "is"],
    ["C:/Users/ASUS/Documents/Get-Deep/data/KnowledgeGraphData/Strunctured/NodesCompany.csv", "c"],
    ["C:/Users/ASUS/Documents/Get-Deep/data/KnowledgeGraphData/Strunctured/NodesIndustry.csv", "i"],
    ["C:/Users/ASUS/Documents/Get-Deep/data/KnowledgeGraphData/Strunctured/NodesSector.csv", "s"],
]

# data = [
#     ["/Users/dimuth/Documents/chat_bot/data_given_anand/company_insdustry_sector_Strunctured/CompanyBELONG_TOIndustry.csv", "ci"],
#     ["/Users/dimuth/Documents/chat_bot/data_given_anand/company_insdustry_sector_Strunctured/CompanyCOMPETES_WITHCompany.csv", "cc"],
#     ["/Users/dimuth/Documents/chat_bot/data_given_anand/company_insdustry_sector_Strunctured/IndustryBELONG_TOSector.csv", "is"],
#     ["/Users/dimuth/Documents/chat_bot/data_given_anand/company_insdustry_sector_Strunctured/NodesCompany.csv", "c"],
#     ["/Users/dimuth/Documents/chat_bot/data_given_anand/company_insdustry_sector_Strunctured/NodesIndustry.csv", "i"],
#     ["/Users/dimuth/Documents/chat_bot/data_given_anand/company_insdustry_sector_Strunctured/NodesSector.csv", "s"],
# ]


# Separate files and keys
files_to_upload = []
keys = []

for path, key in data:
    filename = os.path.basename(path)
    files_to_upload.append(('files', (filename, open(path, 'rb'), 'text/csv')))
    keys.append(key)

# Send POST request
response = requests.post(API_URL, files=files_to_upload, data={'keys': keys})
# Print results
print("Status Code:", response.status_code)
print("Response:", response.text)