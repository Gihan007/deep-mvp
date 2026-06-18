from langchain_core.prompts import PromptTemplate




# company_performance_and_investment_thesis_report_structure = """
# ## Executive Summary & Recommendation
# A concise, single-page summary presenting the final investment recommendation (e.g., Strong Buy, Hold, Sell), the rationale, and the company's competitive ranking.
# ## Detailed Investment Thesis Statement
# Synthesis of the findings into a clear, concluding summary statement justifying the "Buy/Hold/Sell" recommendation and outlining the required conditions for the investment's success.
# ## Economic Moat Assessment
# The report shall contain a dedicated section defining the company's sustainable competitive advantage ("Economic Moat"), categorized (e.g., Wide, Narrow, None) and supported by qualitative evidence (e.g., network effects, brand value, cost advantages).
# ## Industry Disruption Analysis
# The report shall provide an overview of the target company's industry, including overall growth trajectory, key trends, and a specific analysis of any major impending or recent disruptions (technology, regulation, etc.) that could impact the company's moat or growth.
# ## Competitive Context & Peer Identification
# The report shall automatically identify and list 5-10 direct, relevant industry peers.
# ## Relative Performance Benchmarking
# The report shall compare the target company against its identified peers using the following metrics, presented in clear tables and charts: Intrinsic Value vs. Market Value Differential, Return on Invested Capital (ROIC), 5-Year Revenue Growth (CAGR), and Earnings Yield.
# ## Industry Ranking Score
# The report shall calculate and display a clear, quantifiable ranking (e.g., "2nd of 8 Peers") based on the composite strength of the company's core value metrics (FR-2.1.6).
# ## Qualitative & Growth Catalysts
# The report shall synthesize and highlight several key, interesting facts and the latest news that directly impact the company's future growth prospects (last 12 months).
# """




# industry_deep_drive_report_structure = """
# ## Synthesis & Strategic Recommendations
# The initial section shall synthesize all core insights (Market Size, Competitive Forces, Profit Pools, Trends) into a clear, concluding thesis on the industry's overall attractiveness, highlighting 2-3 actionable investment recommendations.
# ## Major Trends & Value Impact Analysis
# A dedicated section analyzing the Top 3 major trends and disruptions (technological, regulatory, or economic) currently affecting the industry. It must include actionable insights on what companies should watch for and a forecast of how these trends will impact the intrinsic value and future potential of companies within the sector.
# ## Industry Segmentation & Size
# The report shall quantify the total addressable market (TAM) for the industry, define its key sub-segments (e.g., geographical, product type), and provide 5-year historical and projected growth rates for the overall market.
# ## Competitive Forces Analysis
# The report shall perform a qualitative and quantitative analysis of the industry structure based on Porter's Five Forces (e.g., Rivalry, New Entrants, Substitutes, Supplier/Buyer Power).
# ## Profit Pool Mapping
# The report shall visually map the industry's value chain, clearly identifying where profit pools are concentrated and predicting potential shifts in value capture over the next 3 years.
# ## Key Drivers and Barriers
# The report shall analyze and list the primary forces driving growth (e.g., demographic shifts, technological adoption) and the major structural barriers to entry and expansion (e.g., regulatory hurdles, capital intensity).
# ## Aggregate Financial Benchmarks
# The report shall present consolidated industry-wide financial metrics, including average ROIC, median debt-to-equity ratio, and average gross profit margin, benchmarked against broader sector data.
# """


def deep_report_generating_agent_human_prompt( report_type,time_horizon, ticker, company_name, industry_name, instructions):


    if report_type == "company_performance_and_investment_thesis":
        missing_data = []
        if company_name:
            if instructions:
                company_name_given_prompt = f"""
                Generate a comprehensive report under title "Company Performance and Investment Thesis" for the company {company_name}
                The report should be based on the time horizon: {time_horizon}.
                use this addition instructions: {instructions}
                This report is designed to address the central question: "Should I buy this company, and why?"
                """
                return {'prompt': company_name_given_prompt, 'missing_data': missing_data}
            else:
                company_name_given_prompt = f"""
                Generate a comprehensive report under title "Company Performance and Investment Thesis" for the company {company_name}
                The report should be based on the time horizon: {time_horizon}.
                This report is designed to address the central question: "Should I buy this company, and why?"
                """
                return {'prompt': company_name_given_prompt, 'missing_data': missing_data}
        if ticker:
            if instructions:
                ticker_given_prompt = f"""
                Generate a comprehensive report under title "Company Performance and Investment Thesis" for the company with ticker {ticker}
                The report should be based on the time horizon: {time_horizon}.
                Use this addition instructions: {instructions}
                This report is designed to address the central question: "Should I buy this company, and why?"
                """
                return {'prompt': ticker_given_prompt, 'missing_data': missing_data}
            else:
                ticker_given_prompt = f"""
                Generate a comprehensive report under title "Company Performance and Investment Thesis" for the company with ticker {ticker}
                The report should be based on the time horizon: {time_horizon}.
                This report is designed to address the central question: "Should I buy this company, and why?"
                """
                return {'prompt': ticker_given_prompt, 'missing_data': missing_data}
        else:
            return {'prompt': None, 'missing_data': ["Company Name or Ticker is missing"]}



    elif report_type == "industry_deep_drive":
        missing_data=[]
        if industry_name:
            if instructions:
                industry_name_given_prompt = f"""
                Generate a comprehensive report under title "Industry Deep Drive" for the industry {industry_name}
                The report should be based on the time horizon: {time_horizon}.
                Use this addition instructions: {instructions}
                This report is designed to provide a comprehensive, top-down analysis of a selected industry, its structure, and its profitability dynamics.
                """
                return {'prompt': industry_name_given_prompt, 'missing_data': missing_data}
            else:
                industry_name_given_prompt = f"""
                Generate a comprehensive report under title Industry Deep Drive for the industry {industry_name}
                The report should be based on the time horizon: {time_horizon}.
                This report is designed to provide a comprehensive, top-down analysis of a selected industry, its structure, and its profitability dynamics.
                """
                return {'prompt': industry_name_given_prompt, 'missing_data': missing_data}
        else:
            return {'prompt': None, 'missing_data': ["Industry Name is missing"]}


    else:
        return {'prompt': None, 'missing_data': ["please provide correct report type"]}
          
        
    




