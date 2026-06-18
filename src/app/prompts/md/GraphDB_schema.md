



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













5. Valuation driver values
   - `(Company)-[:HAS_VALUATION_FORECAST_DRIVER_VALUES]->(:Metric_ValuationForecastDriverValues)`

6. Valuation summary
   - `(Company)-[:HAS_VALUATION_SUMMARY]->(:Metric_ValuationSummary)`








"BalanceInvestedCapital", "SaleOfInvestment", "AssetsAsPercentOfRevenue", "ShortTermInvestments", "ShortTermDebtIssuance", "DeferredRevenueCurrent", "OperatingLeasePrinciplePayment", "OtherOperatingExpenseAsPercentOfRevenue", "StockholdersEquity", "FinanceLeaseNewAssetsObtained", "ReceivablesNoncurrentAsPercentOfRevenue", "OperatingLeaseLiabilities", "UnexplainedChangesInPPEAsPercentOfPPE", "DecreaseInOtherOperatingCapitalNet", "OperatingCash", "LiabilitiesAsPercentOfRevenue", "LiabilitiesNoncurrent", "DecreaseInNoncurrentAssetsNetOfLiabilities", "LiabilitiesCurrent", "GrossCashFlow", "OperatingExpenses", "EBITDA", "FinanceLeaseLiabilitiesCurrentAsPercentOfRevenue", "IncreaseInDeferredRevenue", "DebtIssuance", "VariableLeaseLiabilitiesCurrentAsPercentOfRevenue", "EmployeeRelatedLiabilitiesCurrent", "CapitalExpendituresIncurredButNotYetPaid", "CommonStockAsPercentOfRevenue", "CashAndCashEquivalentsAsPercentOfRevenue", "VariableLeaseLiabilitiesNoncurrent", "NonoperatingIncomeNet", "VariableLeaseLiabilities", "RetainedEarningsAccumulatedDeficit", "TaxOperatingAsPercentOfNOPAT", "DebtToTangibleNetWorth", "CommonStockRepurchasePayment", "ShortTermDebtInclPaper", "DebtToEBITA", "OperatingLeaseRightOfUseAsset", "EBITDAAsPercentOfRevenue", "MinorityShareholderPayment", "CashAndCashEquivalents", "EquityInNoncontrollingInterestsAsPercentOfRevenue", "OtherLiabilitiesCurrentAsPercentOfRevenue", "PaidInCapitalCommonStock", "UnrealizedGainOnInvestmentsAsPercentOfRevenue", "DividendsPayableCurrent", "ImpairmentOfAssetsAndOtherNonCashOperatingActivitiesNet", "DebtAndEquity", "OperatingExpensesAdjusted", "ReceivablesNoncurrent", "DebtAsPercentOfRevenue", "FinanceLeaseAssets", "EffectOfExchangeRate", "DeferredIncomeTaxLiabilitiesNetAsPercentOfTaxProvision", "InterestExpenseDebt", "CashFlowToAllInvestors", "MinBalanceOfShortTermDebtInclPaper", "PreferredStockValue", "AssetImpairmentChargeAsPercentOfRevenue", "ReceivablesNetCurrent", "NetOperatingProfitAfterTaxes", "CashTurnover", "NetIncome", "OperatingCashFlow", "Goodwill", "PaidInCapitalCommonStockAsPercentOfRevenue", "DaysAssetsCurrentAsPercentOfRevenue", "VariableLeaseLiabilitiesCurrent", "Depreciation", "Receivables", "LiabilitiesCurrentAsPercentOfRevenue", "GoodwillAsPercentOfRevenue", "CashAndCashEquivalentsAtCarryingValue", "FinanceLeaseInterestExpenseAsPercentOfRevenue", "PaydownOfShortTermDebtInclPaper", "ShortTermDebtInclPaperAsPercentOfRevenue", "DaysAccruedLiabilitiesCurrentAsPercentOfRevenue", "AssetsCurrent", "DeferredIncomeTaxAssetsNoncurrent", "DecreaseInGoodwill", "GrossMarginAsPercentOfRevenue", "DaysCashAsPercentOfRevenue", "AccruedIncomeTaxesCurrentAsPercentOfPretaxIncome", "InterestIncomeAsPercentOfRevenue", "InvestingCashFlow", "RevenueGrowthRateForecast", "VariableLeaseAmortization", "EBIT", "NetIncomeNoncontrolling", "OtherOperatingExpense", "CommonStockIssuance", "DeferredIncomeTaxAssetsNet", "LongTermDebtPayment", "InterestExpenseIncomeNet", "InterestIncomeAsPercentOfPriorYearExcessCash", "ExcessCash", "AccruedLiabilitiesCurrentAsPercentOfRevenue", "SaleOfBusiness", "RepaymentsOfLongTermDebt", "AssetsNoncurrentAsPercentOfRevenue", "GoodwillImpairment", "NewLeaseDebtIssuances", "VariableLeaseInterestExpenseAsPercentOfPriorYearVariableLeaseLiabilities", "DaysPrepaidExpenseAsPercentOfRevenue", "InventoryTurnover", "OtherAssetsNoncurrent", "NetIncomeControlling", "InterestBurden", "DecreaseInReceivablesCurrent", "ReturnOnInvestedCapitalExclGoodwill", "OperatingLeaseLiabilitiesNoncurrentAsPercentOfRevenue", "PropertyPlantAndEquipmentNet", "ReceivablesCurrent", "EmployeeAccruedLiabilitiesCurrentAsPercentOfRevenue", "Assets", "PropertyPlantAndEquipment", "SellingGeneralAndAdministration", "CashFlowToEquityHolders", "ShortTermDebtPayment", "LeaseAmortization", "NetIncomeLossAttributableToNoncontrollingInterest", "IncomeTaxesPaid", "DecreaseInExcessCash", "CurrentLiabilitiesExclRevolver", "OperatingLeaseCostAsPercentOfRevenue", "PaymentsToAcquirePropertyPlantAndEquipment", "TaxOperating", "InterestExpenseIncomeNetAsPercentOfRevenue", "CommercialPaperAsPercentOfRevenue", "OperatingLeaseCost", "OtherAssetsCurrent", "CommonStockDividendPayment", "DeferredIncomeTaxLiabilitiesNet", "PropertyPlantAndEquipmentTurnover", "UnrealizedGainOnInvestments", "ReceivablesCurrentAsPercentOfRevenue", "TaxProvisionAsPercentOfPretaxIncome", "DaysAccountsPayableCurrentAsPercentOfRevenue", "AccruedIncomeTaxesCurrent", "LeasePrinciplePayments", "OperatingandFinancingLeaseRightofUseAssetAmortization", "OtherNoncashChangesAsPercentOfRevenue", "DecreaseInInventory", "DebtAndDebtEquivalents", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "DaysFinanceLeaseLiabilitiesCurrentAsPercentOfRevenue", "ShareBasedCompensation", "LongTermDebt", "UnexplainedChangesInPPE", "AccumulatedOtherIncomeAsPercentOfRevenue", "DebtToEBITDA", "FinanceLeaseLiabilitiesCurrent", "DaysOtherLiabilitiesCurrentAsPercentOfRevenue", "OperatingLeaseLiabilitiesNoncurrent", "LiabilitiesAndStockholdersEquity", "PaymentsOfDividendsMinorityInterest", "RetainedEarningsAccumulated", "EquityInNoncontrollingInterests", "InvestedCapitalExclGoodwill", "DeferredIncomeTaxLiabilitiesNoncurrent", "OtherAssetsCurrentAsPercentOfRevenue", "AssetsNoncurrent", "AccountsPayableCurrent", "IncreaseInAccruedIncomeTaxes", "EarningsPerShareBasic", "ReturnOnInvestedCapitalInclGoodwill", "TaxBurden", "OtherNoncashChanges", "PretaxIncomeAsPercentOfRevenue", "OperatingIncomeAsPercentOfRevenue", "PaymentsRelatedToTaxWithholdingForShareBasedCompensation", "OtherLiabilitiesCurrent", "AccountsPayableCurrentAsPercentOfRevenue", "OtherLiabilitiesNoncurrent", "FinancingCashFlow", "OperatingLeaseLiabilitiesCurrentAsPercentOfRevenue", "InventoryNet", "CommonStockDividendPaymentAsPercentOfRevenue", "NetCashFlowExclShortTermDebtInclPaper", "FinancingLeasePaymentsAndOtherFinancingActivitiesNet", "PurchaseofNoncontrollingInterest", "NetCashFlow", "NetCashProvidedByUsedInInvestingActivities", "FinanceLeaseAssetsAsPercentOfRevenue", "EmployeeAccruedLiabilitiesCurrent", "VariableLeaseAssets", "FinanceNewLeaseDebtIssuance", "PaymentsForRepurchaseOfCommonStock", "EBITDAToInterest", "ReceivablesTurnover", "IncreaseInOtherLiabilitiesCurrent", "OtherLiabilitiesNoncurrentAsPercentOfRevenue", "EquityAndEquityEquivalents", "WeightedAverageNumberOfDilutedSharesOutstanding", "DaysLiabilitiesCurrentAsPercentOfRevenue", "ShortTermDebtAsPercentOfRevenue", "NonoperatingIncomeNetAsPercentOfRevenue", "FinanceLeaseLiabilities", "NetIncomeLoss", "RetainedEarningsAccumulatedAsPercentOfRevenue", "CapitalExpendituresAsPercentOfRevenue", "NetIncomeAsPercentOfRevenue", "AfterTaxInterestOnDebtAndLeases", "DepreciationAsPercentOfLastYearPPE", "OperaingCurrentAssets", "IncreaseInAccruedLiabilities", "AccruedIncomeTaxesCurrentAsPercentOfRevenue", "ProceedsFromIssuanceOfLongTermDebt", "TaxProvisionAsPercentOfRevenue", "DebtToEquity", "CostOfRevenueAsPercentOfRevenue", "CurrentRatio", "OperatingLeaseNewAssetsObtainedAsPercentOfRevenue", "GrossCashFlowAfterCapitalAndLeaseExpenditures", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect", "DaysEmployeeLiabilitiesCurrentAsPercentOfRevenue", "NonOperatingTaxBenefitOrLoss", "OtherInvestingChanges", "OperatingLeaseLiabilityNoncurrent", "PropertyPlantAndEquipmentAsPercentOfRevenue", "InterestExpense", "FinancingCashFlowExclRevolver", "DaysAccruedIncomeTaxesCurrentAsPercentOfRevenue", "EBITA", "BalanceBalanceSheet", "EquityAsPercentOfRevenue", "FinanceLeaseLiabilitiesNoncurrent", "DeferredIncomeTaxLiabilitiesNetAsPercentOfRevenue", "DaysLongTermDebtCurrentAsPercentOfRevenue", "StockBasedCompensation", "CommonStockIssuanceInclStockBasedCompensation", "IncomeTaxExpenseBenefit", "Liabilities", "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "IncreaseDecreaseInInventories", "PaymentsToMinorityShareholders", "StockBasedCompensationAsPercentOfRevenue", "IncreaseInEmployeeAccruedLiabilities", "AdditionalPaidInCapitalCommonStock", "ProceedsFromSaleAndMaturityOfMarketableSecurities", "AssetsToEquity", "EBITAAsPercentOfRevenue", "ExcessCashAsPercentOfRevenue", "OperatingLeaseInterestExpenseAsPercentOfRevenue", "IncreaseDecreaseInOtherOperatingCapitalNet", "DeferredRevenueCurrentAsPercentOfRevenue", "NetOperatingProfitAfterTaxesAsPercentOfRevenue", "ReturnOnAssets", "LongTermDebtCurrent", "PretaxIncome", "PurchaseOfBusiness", "OperatingLeaseAssets", "OtherNonoperatingIncome", "IncreaseInOtherLiabilitiesNoncurrent", "CashFlowToDebtAndEquityHolders", "FreeCashFlow", "OperatingLeaseInterestExpense", "IntangibleAssetAmortization", "VariableLeaseInterestExpenseAsPercentOfRevenue", "NetCashProvidedByUsedInOperatingActivities", "Debt", "FinanceLeaseInterestExpenseAsPercentOfPriorYearFinanceLeaseLiabilities", "DepreciationAndIntangibleAssetAmortization", "GoodwillImpairmentAsPercentOfRevenue", "GoodwillAsPercentOfInvestedCapital", "CommonStockDividendPaymentAsPercentOfNetIncome", "OtherNonoperatingIncomeAsPercentOfRevenue", "VariableLeaseNewAssetsObtained", "VariableLeaseLiabilitiesNoncurrentAsPercentOfRevenue", "CommonStock", "OperatingCashAsPercentOfRevenue", "DecreaseInOtherAssetsCurrent", "PurchaseOfPPE", "Inventory", "QuickRatio", "InterestExpenseDebtAsPercentOfRevenue", "OperatingLeaseNewAssetsObtained", "SellingGeneralAndAdministrativeExpense", "RepaymentsOfShortTermDebt", "CostOfRevenue", "VariableLeaseAssetsAsPercentOfRevenue", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", "InterestIncome", "AccumulatedOtherIncome", "InvestedCapitalInclGoodwill", "DepreciationAndIntangibleAssetAmortizationAsPercentOfRevenue", "OtherAssetsNoncurrentAsPercentOfRevenue", "AccumulatedOtherComprehensiveIncomeLossNetOfTax", "DecreaseInDeferredIncomeTaxAssets", "NetCashProvidedByUsedInFinancingActivities", "VariableNewLeaseDebtIssuance", "DecreaseInPrepaidExpense", "Equity", "AccountsPayableTurnover", "WeightedAverageNumberOfSharesOutstandingBasic", "FinanceLeasePrinciplePayment", "VariableLeaseCost", "CashAvailableToPayShortTermDebtInclPaper", "OperatingLeaseAssetsAsPercentOfRevenue", "AssetTurnover", "EarningsPerShareDiluted", "PrepaidExpenseAsPercentOfRevenue", "TaxProvision", "FinanceLeaseAmortization", "LongTermDebtNoncurrent", "ProfitLoss", "TaxOperatingAsPercentOfRevenue", "LongTermDebtCurrentAsPercentOfRevenue", "RevenueFromContractWithCustomerExcludingAssessedTax", "OperatingNewLeaseDebtIssuance", "IncreaseInAccountsPayable", "FinanceLeaseLiabilitiesNoncurrentAsPercentOfRevenue", "PaymentsForProceedsFromOtherInvestingActivities", "FinanceLeaseAmortizationAsPercentOfRevenue", "LiabilitiesNoncurrentAsPercentOfRevenue", "VariableLeasePrinciplePayment", "PurchaseOfInvestment", "FixedAssetsAsPercentOfRevenue", "LongTermDebtCurrentAsPercentOfLongTermDebt", "CommonStockValue", "CapitalExpenditures", "DaysOtherAssetsCurrentAsPercentOfRevenue", "OperaingWorkingCapital", "AssetImpairmentCharge", "AccruedLiabilitiesCurrent", "EffectiveTaxRate", "LongTermDebtNoncurrentAsPercentOfRevenue", "InventoryAsPercentOfRevenue", "OperatingIncome", "OperatingLeaseLiabilitiesCurrent", "PaymentsToAcquireShortTermInvestments", "IncreaseInDeferredIncomeTaxLiabilities", "SGAAsPercentOfRevenue", "NetIncomeNoncontrollingAsPercentOfRevenue", "InterestPaidNet", "EffectiveInterestRate", "VariableLeaseCostAsPercentOfRevenue", "OperatingIncomeLoss", "UnexplainedChangesInPPEAsPercentOfRevenue", "InterestAndOtherIncome", "IncreaseDecreaseInAccountsPayable", "DecreaseInWorkingCapital", "OperatingLeaseAmortization", "LongTermDebtAsPercentOfRevenue", "LongTermDebtIssuance", "OperatingIncomeOrEBITAsPercentOfRevenue", "CashFlowToDebtHolders", "ResearchAndDevelopmentAsPercentOfRevenue", "DaysOperatingLeaseLiabilitiesCurrentAsPercentOfRevenue", "IntangibleAssetAmortizationAsPercentOfRevenue", "AssetsCurrentAsPercentOfRevenue", "ReceivablesAsPercentOfRevenue", "GrossMargin", "LiabilitiesAndEquity", "SaleOfPPE", "PaymentsOfDividendsCommonStock", "DecreaseInOtherAssetsNoncurrent", "VariableLeaseInterestExpense", "MinorityDividendPayment", "OperatingLeaseAmortizationAsPercentOfRevenue", "ReturnOnEquity", "OperaingCurrentLiabilities", "NetIncomeControllingAsPercentOfRevenue", "TotalFundsInvested", "IncreaseInDeferredIncomeTaxLiabilitiesNet", "InterestExpenseAsPercentOfRevenue", "LeaseAmortizationAsPercentOfRevenue", "DaysReceivablesCurrentAsPercentOfRevenue", "OperatingExpensesAsPercentOfRevenue", "CommonStockRepurchasePaymentAsPercentOfNetIncome", "ProceedsFromShortTermDebt", "CostOfGoodsAndServicesSold", "ResearchAndDevelopment", "DaysInventoryAsPercentOfRevenue", "PrepaidExpense", "FinanceLeaseInterestExpense", "DecreaseInReceivablesNoncurrent", "FinanceLeaseNewAssetsObtainedAsPercentOfRevenue", "Revenue", "TaxWithholdingPayment", "DepreciationDepletionAndAmortization", "DecreaseInOperatingCash", "CommonStockRepurchasePaymentAsPercentOfRevenue", "DaysDeferredRevenueCurrentAsPercentOfRevenue"
