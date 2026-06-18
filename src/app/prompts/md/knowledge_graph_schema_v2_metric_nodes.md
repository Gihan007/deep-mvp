# Knowledge Graph Schema v2 — Metric Nodes

This file documents each **metric-related node type** in the same style as the previous schema (properties + exact allowed `metricName` list).

---

## Relationship Types and Directions (v2)

1. `(Company)-[:BELONG_TO]->(Industry)`  
   Companies are classified into specific industries.

2. `(Industry)-[:BELONG_TO]->(Sector)`  
   Industries are grouped into broader sectors.

3. Structured metrics (historical)
   - `(Company)-[:HAS_METRIC]->(:Metric_3StatementModel)`
   - `(Company)-[:HAS_METRIC]->(:Metric_FreeCashFlows)`
   - `(Company)-[:HAS_METRIC]->(:Metric_InvestedCapital)`
   - `(Company)-[:HAS_METRIC]->(:Metric_Performance)`
   - `(Company)-[:HAS_METRIC]->(:Metric_HistoricalFinancials)`

4. Structured metrics (predicted)
   - `(Company)-[:HAS_PREDICTED_METRIC]->(:Metric_3StatementModel_Predicted)`
   - `(Company)-[:HAS_PREDICTED_METRIC]->(:Metric_FreeCashFlows_Predicted)`
   - `(Company)-[:HAS_PREDICTED_METRIC]->(:Metric_InvestedCapital_Predicted)`
   - `(Company)-[:HAS_PREDICTED_METRIC]->(:Metric_Performance_Predicted)`

Example query:
```cypher
MATCH (c:Company {ticker:$ticker})-[:HAS_METRIC]->(m:Metric_3StatementModel {metricName:"Revenue"})
RETURN m
```

5. Valuation driver values
   - `(Company)-[:HAS_VALUATION_FORECAST_DRIVER_VALUES]->(:Metric_ValuationForecastDriverValues)`

6. Valuation summary
   - `(Company)-[:HAS_VALUATION_SUMMARY]->(:Metric_ValuationSummary)`

7. `(Company)-[:COMPETE_WITH]-(Company)`  
   Companies that compete in the same market/industry. This relationship is bidirectional.

---

## 4. Metric_3StatementModel Nodes (Label: "Metric_3StatementModel") and Predicted Metric_3StatementModel Nodes (Label: "Metric_3StatementModel_Predicted")**

- Note: Both labels share the same schema, except that year_<YYYY> properties for historical years belong to Metric_3StatementModel nodes, while year_<YYYY> properties for future years belong to Metric_3StatementModel_Predicted nodes.
- Properties:
  - `metricKey` (str) — unique identifier (MERGE key)
  - `ticker` (str) — company ticker
  - `datasetKey` (str) — always "3StatementModel"
  - `metricName` (str) — metric name (exact, from CSV first column)
  - `DriverValue` (number)
  - `year_YYYY` (number) — year values (historical + forecast years)

  **Available `metricName` values (USE EXACT NAMES)**
  ```
  "RevenueGrowthRateForecast", "Revenue", "CostOfRevenue", "GrossMargin", "SellingGeneralAndAdministration", "Depreciation", "IntangibleAssetAmortization", "DepreciationAndIntangibleAssetAmortization", "OperatingLeaseAmortization", "FinanceLeaseAmortization", "VariableLeaseAmortization", "LeaseAmortization", "ResearchAndDevelopment", "GoodwillImpairment", "OtherOperatingExpense", "OperatingExpenses", "VariableLeaseCost", "OperatingExpensesAdjusted", "OperatingIncome", "InterestExpenseDebt", "OperatingLeaseInterestExpense", "FinanceLeaseInterestExpense", "VariableLeaseInterestExpense", "InterestExpense", "InterestIncome", "InterestExpenseIncomeNet", "OtherNonoperatingIncome", "NonoperatingIncomeNet", "PretaxIncome", "TaxProvision", "NetIncomeControlling", "NetIncomeNoncontrolling", "NetIncome", "AssetImpairmentCharge", "UnrealizedGainOnInvestments", "OtherNoncashChanges", "StockBasedCompensation", "CommonStockDividendPayment", "CommonStockRepurchasePayment", "EBIT", "EBITA", "EBITDA", "TaxOperating", "NetOperatingProfitAfterTaxes", "OperatingLeaseCost", "CapitalExpenditures", "UnexplainedChangesInPPE", "CashAndCashEquivalents", "ReceivablesCurrent", "Inventory", "PrepaidExpense", "OtherAssetsCurrent", "AssetsCurrent", "PropertyPlantAndEquipment", "OperatingLeaseAssets", "FinanceLeaseAssets", "VariableLeaseAssets", "Goodwill", "DeferredIncomeTaxAssetsNoncurrent", "ReceivablesNoncurrent", "OtherAssetsNoncurrent", "AssetsNoncurrent", "Assets", "AccountsPayableCurrent", "EmployeeAccruedLiabilitiesCurrent", "AccruedLiabilitiesCurrent", "AccruedIncomeTaxesCurrent", "DeferredRevenueCurrent", "ShortTermDebtInclPaper", "LongTermDebtCurrent", "OperatingLeaseLiabilitiesCurrent", "FinanceLeaseLiabilitiesCurrent", "VariableLeaseLiabilitiesCurrent", "OtherLiabilitiesCurrent", "LiabilitiesCurrent", "LongTermDebtNoncurrent", "OperatingLeaseLiabilitiesNoncurrent", "FinanceLeaseLiabilitiesNoncurrent", "VariableLeaseLiabilitiesNoncurrent", "DeferredIncomeTaxLiabilitiesNoncurrent", "DeferredIncomeTaxLiabilitiesNet", "OtherLiabilitiesNoncurrent", "LiabilitiesNoncurrent", "Liabilities", "CommonStock", "PaidInCapitalCommonStock", "AccumulatedOtherIncome", "RetainedEarningsAccumulated", "Equity", "EquityInNoncontrollingInterests", "LiabilitiesAndEquity", "BalanceBalanceSheet", "OperatingCash", "ExcessCash", "OperatingLeaseNewAssetsObtained", "FinanceLeaseNewAssetsObtained", "VariableLeaseNewAssetsObtained", "Receivables", "LongTermDebt", "Debt", "CurrentLiabilitiesExclRevolver", "OperatingCashFlow", "DecreaseInReceivablesCurrent", "DecreaseInInventory", "DecreaseInPrepaidExpense", "DecreaseInOtherAssetsCurrent", "DecreaseInDeferredIncomeTaxAssets", "DecreaseInReceivablesNoncurrent", "DecreaseInOtherAssetsNoncurrent", "IncreaseInAccountsPayable", "IncreaseInEmployeeAccruedLiabilities", "IncreaseInAccruedLiabilities", "IncreaseInAccruedIncomeTaxes", "IncreaseInDeferredRevenue", "IncreaseInOtherLiabilitiesCurrent", "IncreaseInDeferredIncomeTaxLiabilities", "IncreaseInDeferredIncomeTaxLiabilitiesNet", "IncreaseInOtherLiabilitiesNoncurrent", "DecreaseInOtherOperatingCapitalNet", "InvestingCashFlow", "PurchaseOfPPE", "SaleOfPPE", "PurchaseOfBusiness", "SaleOfBusiness", "PurchaseOfInvestment", "SaleOfInvestment", "OtherInvestingChanges", "FinancingCashFlow", "ShortTermDebtIssuance", "ShortTermDebtPayment", "LongTermDebtIssuance", "LongTermDebtPayment", "CommonStockIssuance", "TaxWithholdingPayment", "OperatingNewLeaseDebtIssuance", "OperatingLeasePrinciplePayment", "FinanceNewLeaseDebtIssuance", "FinanceLeasePrinciplePayment", "VariableNewLeaseDebtIssuance", "VariableLeasePrinciplePayment", "MinorityDividendPayment", "MinorityShareholderPayment", "PurchaseofNoncontrollingInterest", "EffectOfExchangeRate", "NetCashFlow", "FinancingCashFlowExclRevolver", "NetCashFlowExclShortTermDebtInclPaper", "CashAvailableToPayShortTermDebtInclPaper", "MinBalanceOfShortTermDebtInclPaper", "PaydownOfShortTermDebtInclPaper"
  ```

## 5. Metric_FreeCashFlows Nodes (Label: "Metric_FreeCashFlows") and Predicted Metric_FreeCashFlows Nodes (Label: "Metric_FreeCashFlows_Predicted")**

- Note: Both labels share the same schema, except that year_<YYYY> properties for historical years belong to Metric_FreeCashFlows nodes, while year_<YYYY> properties for future years belong to Metric_FreeCashFlows_Predicted nodes.
- Properties:
  - `metricKey` (str) — unique identifier (MERGE key)
  - `ticker` (str) — company ticker
  - `datasetKey` (str) — always "FreeCashFlows"
  - `metricName` (str) — metric name (exact, from CSV first column)
  - `year_YYYY` (number) — year values (historical + forecast years)

  **Available `metricName` values (USE EXACT NAMES)**
  ```
  "NetOperatingProfitAfterTaxes", "DepreciationAndIntangibleAssetAmortization", "OperatingLeaseAmortization", "FinanceLeaseAmortization", "VariableLeaseAmortization", "AssetImpairmentCharge", "UnrealizedGainOnInvestments", "OtherNoncashChanges", "GrossCashFlow", "CapitalExpenditures", "OperatingLeaseNewAssetsObtained", "FinanceLeaseNewAssetsObtained", "VariableLeaseNewAssetsObtained", "GrossCashFlowAfterCapitalAndLeaseExpenditures", "DecreaseInOperatingCash", "DecreaseInReceivablesCurrent", "DecreaseInInventory", "DecreaseInPrepaidExpense", "DecreaseInOtherAssetsCurrent", "IncreaseInAccountsPayable", "IncreaseInEmployeeAccruedLiabilities", "IncreaseInAccruedLiabilities", "IncreaseInAccruedIncomeTaxes", "IncreaseInDeferredRevenue", "IncreaseInOtherLiabilitiesCurrent", "DecreaseInWorkingCapital", "DecreaseInOtherAssetsNoncurrent", "IncreaseInOtherLiabilitiesNoncurrent", "IncreaseInDeferredIncomeTaxLiabilitiesNet", "DecreaseInReceivablesNoncurrent", "DecreaseInGoodwill", "DecreaseInNoncurrentAssetsNetOfLiabilities", "FreeCashFlow", "InterestIncome", "OtherNonoperatingIncome", "DecreaseInExcessCash", "NonOperatingTaxBenefitOrLoss", "CashFlowToAllInvestors", "AfterTaxInterestOnDebtAndLeases", "DebtIssuance", "LeasePrinciplePayments", "NewLeaseDebtIssuances", "CashFlowToDebtHolders", "CommonStockDividendPayment", "CommonStockRepurchasePayment", "CommonStockIssuanceInclStockBasedCompensation", "MinorityDividendPayment", "MinorityShareholderPayment", "CashFlowToEquityHolders", "CashFlowToDebtAndEquityHolders"
  ```

## 6. Metric_InvestedCapital Nodes (Label: "Metric_InvestedCapital") and Predicted Metric_InvestedCapital Nodes (Label: "Metric_InvestedCapital_Predicted")**

- Note: Both labels share the same schema, except that year_<YYYY> properties for historical years belong to Metric_InvestedCapital nodes, while year_<YYYY> properties for future years belong to Metric_InvestedCapital_Predicted nodes.
- Properties:
  - `metricKey` (str) — unique identifier (MERGE key)
  - `ticker` (str) — company ticker
  - `datasetKey` (str) — always "InvestedCapital"
  - `metricName` (str) — metric name (exact, from CSV first column)
  - `year_YYYY` (number) — year values (historical + forecast years)

  **Available `metricName` values (USE EXACT NAMES)**
  ```
  "OperatingCash", "ReceivablesCurrent", "Inventory", "PrepaidExpense", "OtherAssetsCurrent", "OperaingCurrentAssets", "AccountsPayableCurrent", "EmployeeAccruedLiabilitiesCurrent", "AccruedLiabilitiesCurrent", "AccruedIncomeTaxesCurrent", "DeferredRevenueCurrent", "OtherLiabilitiesCurrent", "OperaingCurrentLiabilities", "OperaingWorkingCapital", "PropertyPlantAndEquipment", "OperatingLeaseAssets", "FinanceLeaseAssets", "VariableLeaseAssets", "ReceivablesNoncurrent", "OtherAssetsNoncurrent", "OtherLiabilitiesNoncurrent", "InvestedCapitalExclGoodwill", "Goodwill", "InvestedCapitalInclGoodwill", "ExcessCash", "DeferredIncomeTaxAssetsNet", "TotalFundsInvested", "ShortTermDebtInclPaper", "LongTermDebt", "OperatingLeaseLiabilities", "FinanceLeaseLiabilities", "VariableLeaseLiabilities", "DebtAndDebtEquivalents", "Equity", "EquityInNoncontrollingInterests", "EquityAndEquityEquivalents", "DebtAndEquity", "BalanceInvestedCapital"
  ```

## 7. Metric_Performance Nodes (Label: "Metric_Performance") and Predicted Metric_Performance Nodes (Label: "Metric_Performance_Predicted")**

- Note: Both labels share the same schema, except that year_<YYYY> properties for historical years belong to Metric_Performance nodes, while year_<YYYY> properties for future years belong to Metric_Performance_Predicted nodes.
- Properties:
  - `metricKey` (str) — unique identifier (MERGE key)
  - `ticker` (str) — company ticker
  - `datasetKey` (str) — always "Performance"
  - `metricName` (str) — metric name (exact, from CSV first column)
  - `year_YYYY` (number) — year values (historical + forecast years)

  **Available `metricName` values (USE EXACT NAMES)**
  ```
  "OperatingIncomeAsPercentOfRevenue", "FixedAssetsAsPercentOfRevenue", "ReturnOnInvestedCapitalExclGoodwill", "GoodwillAsPercentOfInvestedCapital", "ReturnOnInvestedCapitalInclGoodwill", "ReturnOnEquity", "ReturnOnAssets", "GrossMarginAsPercentOfRevenue", "NetIncomeAsPercentOfRevenue", "EffectiveInterestRate", "InterestBurden", "EffectiveTaxRate", "TaxBurden", "AssetTurnover", "PropertyPlantAndEquipmentTurnover", "CashTurnover", "ReceivablesTurnover", "InventoryTurnover", "AccountsPayableTurnover", "AssetsToEquity", "DebtToEquity", "DebtToTangibleNetWorth", "DebtToEBITA", "DebtToEBITDA", "CurrentRatio", "QuickRatio", "EBITDAToInterest", "CostOfRevenueAsPercentOfRevenue", "SGAAsPercentOfRevenue", "DepreciationAsPercentOfLastYearPPE", "IntangibleAssetAmortizationAsPercentOfRevenue", "DepreciationAndIntangibleAssetAmortizationAsPercentOfRevenue", "OperatingLeaseInterestExpenseAsPercentOfRevenue", "OperatingLeaseAmortizationAsPercentOfRevenue", "FinanceLeaseAmortizationAsPercentOfRevenue", "VariableLeaseCostAsPercentOfRevenue", "LeaseAmortizationAsPercentOfRevenue", "ResearchAndDevelopmentAsPercentOfRevenue", "GoodwillImpairmentAsPercentOfRevenue", "OtherOperatingExpenseAsPercentOfRevenue", "OperatingExpensesAsPercentOfRevenue", "OperatingIncomeOrEBITAsPercentOfRevenue", "InterestExpenseDebtAsPercentOfRevenue", "FinanceLeaseInterestExpenseAsPercentOfRevenue", "FinanceLeaseInterestExpenseAsPercentOfPriorYearFinanceLeaseLiabilities", "VariableLeaseInterestExpenseAsPercentOfRevenue", "VariableLeaseInterestExpenseAsPercentOfPriorYearVariableLeaseLiabilities", "InterestExpenseAsPercentOfRevenue", "InterestIncomeAsPercentOfRevenue", "InterestIncomeAsPercentOfPriorYearExcessCash", "InterestExpenseIncomeNetAsPercentOfRevenue", "OtherNonoperatingIncomeAsPercentOfRevenue", "NonoperatingIncomeNetAsPercentOfRevenue", "PretaxIncomeAsPercentOfRevenue", "TaxProvisionAsPercentOfRevenue", "TaxProvisionAsPercentOfPretaxIncome", "NetIncomeControllingAsPercentOfRevenue", "NetIncomeNoncontrollingAsPercentOfRevenue", "AssetImpairmentChargeAsPercentOfRevenue", "UnrealizedGainOnInvestmentsAsPercentOfRevenue", "OtherNoncashChangesAsPercentOfRevenue", "StockBasedCompensationAsPercentOfRevenue", "CommonStockDividendPaymentAsPercentOfRevenue", "CommonStockDividendPaymentAsPercentOfNetIncome", "CommonStockRepurchasePaymentAsPercentOfRevenue", "CommonStockRepurchasePaymentAsPercentOfNetIncome", "EBITAAsPercentOfRevenue", "EBITDAAsPercentOfRevenue", "TaxOperatingAsPercentOfRevenue", "TaxOperatingAsPercentOfNOPAT", "NetOperatingProfitAfterTaxesAsPercentOfRevenue", "OperatingLeaseCostAsPercentOfRevenue", "CapitalExpendituresAsPercentOfRevenue", "UnexplainedChangesInPPEAsPercentOfRevenue", "UnexplainedChangesInPPEAsPercentOfPPE", "CashAndCashEquivalentsAsPercentOfRevenue", "ReceivablesCurrentAsPercentOfRevenue", "InventoryAsPercentOfRevenue", "PrepaidExpenseAsPercentOfRevenue", "OtherAssetsCurrentAsPercentOfRevenue", "AssetsCurrentAsPercentOfRevenue", "PropertyPlantAndEquipmentAsPercentOfRevenue", "OperatingLeaseAssetsAsPercentOfRevenue", "FinanceLeaseAssetsAsPercentOfRevenue", "VariableLeaseAssetsAsPercentOfRevenue", "GoodwillAsPercentOfRevenue", "ReceivablesNoncurrentAsPercentOfRevenue", "OtherAssetsNoncurrentAsPercentOfRevenue", "AssetsNoncurrentAsPercentOfRevenue", "AssetsAsPercentOfRevenue", "AccountsPayableCurrentAsPercentOfRevenue", "EmployeeAccruedLiabilitiesCurrentAsPercentOfRevenue", "AccruedLiabilitiesCurrentAsPercentOfRevenue", "AccruedIncomeTaxesCurrentAsPercentOfRevenue", "AccruedIncomeTaxesCurrentAsPercentOfPretaxIncome", "DeferredRevenueCurrentAsPercentOfRevenue", "ShortTermDebtAsPercentOfRevenue", "CommercialPaperAsPercentOfRevenue", "ShortTermDebtInclPaperAsPercentOfRevenue", "LongTermDebtCurrentAsPercentOfRevenue", "LongTermDebtCurrentAsPercentOfLongTermDebt", "OperatingLeaseLiabilitiesCurrentAsPercentOfRevenue", "FinanceLeaseLiabilitiesCurrentAsPercentOfRevenue", "VariableLeaseLiabilitiesCurrentAsPercentOfRevenue", "OtherLiabilitiesCurrentAsPercentOfRevenue", "LiabilitiesCurrentAsPercentOfRevenue", "LongTermDebtNoncurrentAsPercentOfRevenue", "OperatingLeaseLiabilitiesNoncurrentAsPercentOfRevenue", "FinanceLeaseLiabilitiesNoncurrentAsPercentOfRevenue", "VariableLeaseLiabilitiesNoncurrentAsPercentOfRevenue", "DeferredIncomeTaxLiabilitiesNetAsPercentOfRevenue", "DeferredIncomeTaxLiabilitiesNetAsPercentOfTaxProvision", "OtherLiabilitiesNoncurrentAsPercentOfRevenue", "LiabilitiesNoncurrentAsPercentOfRevenue", "LiabilitiesAsPercentOfRevenue", "CommonStockAsPercentOfRevenue", "PaidInCapitalCommonStockAsPercentOfRevenue", "AccumulatedOtherIncomeAsPercentOfRevenue", "RetainedEarningsAccumulatedAsPercentOfRevenue", "EquityAsPercentOfRevenue", "EquityInNoncontrollingInterestsAsPercentOfRevenue", "OperatingLeaseNewAssetsObtainedAsPercentOfRevenue", "FinanceLeaseNewAssetsObtainedAsPercentOfRevenue", "DaysCashAsPercentOfRevenue", "DaysReceivablesCurrentAsPercentOfRevenue", "DaysInventoryAsPercentOfRevenue", "DaysPrepaidExpenseAsPercentOfRevenue", "DaysOtherAssetsCurrentAsPercentOfRevenue", "DaysAssetsCurrentAsPercentOfRevenue", "DaysAccountsPayableCurrentAsPercentOfRevenue", "DaysEmployeeLiabilitiesCurrentAsPercentOfRevenue", "DaysAccruedLiabilitiesCurrentAsPercentOfRevenue", "DaysAccruedIncomeTaxesCurrentAsPercentOfRevenue", "DaysDeferredRevenueCurrentAsPercentOfRevenue", "DaysLongTermDebtCurrentAsPercentOfRevenue", "DaysOperatingLeaseLiabilitiesCurrentAsPercentOfRevenue", "DaysFinanceLeaseLiabilitiesCurrentAsPercentOfRevenue", "DaysOtherLiabilitiesCurrentAsPercentOfRevenue", "DaysLiabilitiesCurrentAsPercentOfRevenue", "OperatingCashAsPercentOfRevenue", "ExcessCashAsPercentOfRevenue", "ReceivablesAsPercentOfRevenue", "LongTermDebtAsPercentOfRevenue", "DebtAsPercentOfRevenue"
  ```

## 8. Metric_HistoricalFinancials Nodes (Label: "Metric_HistoricalFinancials")**

- Note: This dataset is ingested as historical-only into `Metric_HistoricalFinancials`.
- Properties:
  - `metricKey` (str) — unique identifier (MERGE key)
  - `ticker` (str) — company ticker
  - `datasetKey` (str) — always "HistoricalFinancials"
  - `metricName` (str) — metric name (exact, from CSV first column)
  - `statementType` (str) — statement type (IncomeStatement / BalanceSheet / CashFlows)
  - `year_YYYY` (number) — year values

  **Available `metricName` values (USE EXACT NAMES)**
  ```
  "RevenueFromContractWithCustomerExcludingAssessedTax", "CostOfGoodsAndServicesSold", "SellingGeneralAndAdministrativeExpense", "OperatingIncomeLoss", "InterestExpense", "InterestAndOtherIncome", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", "IncomeTaxExpenseBenefit", "ProfitLoss", "NetIncomeLossAttributableToNoncontrollingInterest", "NetIncomeLoss", "EarningsPerShareBasic", "EarningsPerShareDiluted", "WeightedAverageNumberOfSharesOutstandingBasic", "WeightedAverageNumberOfDilutedSharesOutstanding", "CashAndCashEquivalentsAtCarryingValue", "ShortTermInvestments", "ReceivablesNetCurrent", "InventoryNet", "OtherAssetsCurrent", "AssetsCurrent", "PropertyPlantAndEquipmentNet", "OperatingLeaseRightOfUseAsset", "OtherAssetsNoncurrent", "Assets", "AccountsPayableCurrent", "EmployeeRelatedLiabilitiesCurrent", "AccruedLiabilitiesCurrent", "DeferredRevenueCurrent", "LongTermDebtCurrent", "OtherLiabilitiesCurrent", "LiabilitiesCurrent", "LongTermDebtNoncurrent", "OperatingLeaseLiabilityNoncurrent", "OtherLiabilitiesNoncurrent", "Liabilities", "PreferredStockValue", "CommonStockValue", "AdditionalPaidInCapitalCommonStock", "AccumulatedOtherComprehensiveIncomeLossNetOfTax", "RetainedEarningsAccumulatedDeficit", "StockholdersEquity", "LiabilitiesAndStockholdersEquity", "DepreciationDepletionAndAmortization", "OperatingandFinancingLeaseRightofUseAssetAmortization", "ShareBasedCompensation", "ImpairmentOfAssetsAndOtherNonCashOperatingActivitiesNet", "IncreaseDecreaseInInventories", "IncreaseDecreaseInAccountsPayable", "IncreaseDecreaseInOtherOperatingCapitalNet", "NetCashProvidedByUsedInOperatingActivities", "PaymentsToAcquireShortTermInvestments", "ProceedsFromSaleAndMaturityOfMarketableSecurities", "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsForProceedsFromOtherInvestingActivities", "NetCashProvidedByUsedInInvestingActivities", "RepaymentsOfShortTermDebt", "ProceedsFromShortTermDebt", "RepaymentsOfLongTermDebt", "ProceedsFromIssuanceOfLongTermDebt", "PaymentsRelatedToTaxWithholdingForShareBasedCompensation", "PaymentsForRepurchaseOfCommonStock", "PaymentsOfDividendsCommonStock", "FinancingLeasePaymentsAndOtherFinancingActivitiesNet", "PaymentsOfDividendsMinorityInterest", "PaymentsToMinorityShareholders", "NetCashProvidedByUsedInFinancingActivities", "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "InterestPaidNet", "IncomeTaxesPaid", "DividendsPayableCurrent", "CapitalExpendituresIncurredButNotYetPaid"
  ```

## 9. Metric_ValuationForecastDriverValues Node (Label: "Metric_ValuationForecastDriverValues")**

- Properties:
  - `metricKey` (str)
  - `ticker` (str)
  - `datasetKey` (str) — always "ValuationForecastDriverValues"
  - `metricName` (str) — always "ValuationForecastDriverValues"
  - `ExtractionTime` (str)
  - `RevenueGrowthInLast4y` (number)
  - `RevenueGrowth5y` (number)
  - `RevenueGrowth10y` (number)
  - `NOPATGrowthRateInPerpetuity` (number)
  - `OperatingTaxRate` (number)
  - `PretaxCostOfDebt` (number)
  - `WeightedAverageCostofCapital` (number)
  - `ReturnOnNewInvestedCapital` (number)
  - `ValueOfCarryforwardCredits` (number)
  - `GrossMarginAsPercentOfRevenue` (number)
  - `SGAAsPercentOfRevenue` (number)
  - `CapitalExpendituresAsPercentOfRevenue` (number)
  - `DepreciationAsPercentOfLastYearPPE` (number)
  - `IntangibleAssetAmortizationAsPercentOfRevenue` (number)
  - `FinanceLeaseTerm` (number)
  - `FinanceLeaseIntensity` (number)
  - `OperatingLeaseDiscountRate` (number)
  - `OperatingLeaseIntensity` (number)
  - `OperatingLeaseCostAsPercentOfRevenue` (number)
  - `OperatingLeaseLiabilitiesNoncurrentAsPercentOfRevenue` (number)
  - `FinanceLeaseDiscountRate` (number)
  - `FinanceLeaseLiabilitiesCurrentAsPercentOfRevenue` (number)
  - `FinanceLeaseLiabilitiesNoncurrentAsPercentOfRevenue` (number)
  - `VariableLeaseCostAsPercentOfRevenue` (number)
  - `ResearchAndDevelopmentAsPercentOfRevenue` (number)
  - `OtherOperatingExpenseAsPercentOfRevenue` (number)
  - `InterestIncomeAsPercentOfPriorYearExcessCash` (number)
  - `OtherNonoperatingIncomeAsPercentOfRevenue` (number)
  - `TaxProvisionAsPercentOfPretaxIncome` (number)
  - `NetIncomeNoncontrollingAsPercentOfRevenue` (number)
  - `StockBasedCompensationAsPercentOfRevenue` (number)
  - `CommonStockDividendPaymentAsPercentOfNetIncome` (number)
  - `CommonStockRepurchasePayment` (number)
  - `ReceivablesCurrentAsPercentOfRevenue` (number)
  - `InventoryAsPercentOfRevenue` (number)
  - `PrepaidExpenseAsPercentOfRevenue` (number)
  - `OtherAssetsCurrentAsPercentOfRevenue` (number)
  - `ReceivablesNoncurrentAsPercentOfRevenue` (number)
  - `OtherAssetsNoncurrentAsPercentOfRevenue` (number)
  - `AccountsPayableCurrentAsPercentOfRevenue` (number)
  - `EmployeeAccruedLiabilitiesCurrentAsPercentOfRevenue` (number)
  - `AccruedLiabilitiesCurrentAsPercentOfRevenue` (number)
  - `AccruedIncomeTaxesCurrentAsPercentOfPretaxIncome` (number)
  - `DeferredRevenueCurrentAsPercentOfRevenue` (number)
  - `LongTermDebtCurrentAsPercentOfRevenue` (number)
  - `OtherLiabilitiesCurrentAsPercentOfRevenue` (number)
  - `LongTermDebtNoncurrentAsPercentOfRevenue` (number)
  - `OtherLiabilitiesNoncurrentAsPercentOfRevenue` (number)
  - `OperatingCashAsPercentOfRevenue` (number)

  **Available `metricName` values (USE EXACT NAMES)**
  ```
  "ValuationForecastDriverValues"
  ```

## 10. Metric_ValuationSummary Node (Label: "Metric_ValuationSummary")**

- Properties:
  - `metricKey` (str)
  - `ticker` (str)
  - `datasetKey` (str) — always "ValuationSummary"
  - `metricName` (str) — always "ValuationSummary"
  - Flattened value properties (generated from CSV rows):
    - `<RowName>_<ColumnName>` where ColumnName is one of: `FreeCashFlow`, `DiscountFactor`, `PresentValue`

  **Flattened property keys present in the reference CSV (COST)**
  ```
  2026_DiscountFactor
  2026_FreeCashFlow
  2026_PresentValue
  2027_DiscountFactor
  2027_FreeCashFlow
  2027_PresentValue
  2028_DiscountFactor
  2028_FreeCashFlow
  2028_PresentValue
  2029_DiscountFactor
  2029_FreeCashFlow
  2029_PresentValue
  2030_DiscountFactor
  2030_FreeCashFlow
  2030_PresentValue
  2031_DiscountFactor
  2031_FreeCashFlow
  2031_PresentValue
  2032_DiscountFactor
  2032_FreeCashFlow
  2032_PresentValue
  2033_DiscountFactor
  2033_FreeCashFlow
  2033_PresentValue
  2034_DiscountFactor
  2034_FreeCashFlow
  2034_PresentValue
  2035_DiscountFactor
  2035_FreeCashFlow
  2035_PresentValue
  2036_DiscountFactor
  2036_FreeCashFlow
  2036_PresentValue
  AdjustedValueOfOperations_DiscountFactor
  AdjustedValueOfOperations_FreeCashFlow
  AdjustedValueOfOperations_PresentValue
  Debt_DiscountFactor
  Debt_FreeCashFlow
  Debt_PresentValue
  EnterpriseValue_DiscountFactor
  EnterpriseValue_FreeCashFlow
  EnterpriseValue_PresentValue
  EquityIntrinsicValue_DiscountFactor
  EquityIntrinsicValue_FreeCashFlow
  EquityIntrinsicValue_PresentValue
  ExcessCash_DiscountFactor
  ExcessCash_FreeCashFlow
  ExcessCash_PresentValue
  FinanceLeaseLiabilities_DiscountFactor
  FinanceLeaseLiabilities_FreeCashFlow
  FinanceLeaseLiabilities_PresentValue
  MidyearAdjustmentFactor_DiscountFactor
  MidyearAdjustmentFactor_FreeCashFlow
  MidyearAdjustmentFactor_PresentValue
  NOPATGrowthRateInPerpetuity_DiscountFactor
  NOPATGrowthRateInPerpetuity_FreeCashFlow
  NOPATGrowthRateInPerpetuity_PresentValue
  OperatingLeaseLiabilities_DiscountFactor
  OperatingLeaseLiabilities_FreeCashFlow
  OperatingLeaseLiabilities_PresentValue
  ReturnOnNewInvestedCapital_DiscountFactor
  ReturnOnNewInvestedCapital_FreeCashFlow
  ReturnOnNewInvestedCapital_PresentValue
  ValueOfOperations_DiscountFactor
  ValueOfOperations_FreeCashFlow
  ValueOfOperations_PresentValue
  VariableLeaseLiabilities_DiscountFactor
  VariableLeaseLiabilities_FreeCashFlow
  VariableLeaseLiabilities_PresentValue
  WeightedAverageCostofCapital_DiscountFactor
  WeightedAverageCostofCapital_FreeCashFlow
  WeightedAverageCostofCapital_PresentValue
  ```

  **Available `metricName` values (USE EXACT NAMES)**
  ```
  "ValuationSummary"
  ```
