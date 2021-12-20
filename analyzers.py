import backtrader as bt

class CAGRAnalyzer(bt.analyzers.Analyzer):
    """
    Analyzer returning CAGR of the portfolio
    """

    def nextstart(self):
        self.rets = bt.AutoOrderedDict()
        self.rets.start_value = self.strategy.broker.getvalue()
        self.rets.start_date = self.strategy.datetime.datetime().date()

    def stop(self):
        self.rets.end_value = self.strategy.broker.getvalue()
        self.rets.end_date = self.strategy.datetime.datetime().date()
        self.rets.num_years = (self.rets.end_date - self.rets.start_date).days / 365.25
        self.rets.cagr = self.calculate_cagr(self.rets.start_value, self.rets.end_value, self.rets.num_years)

    def calculate_cagr(self, start_value, end_value, num_years):
        """
        The CAGR formula is: 
            EV / BV ^ (1/n) – 1. 
        EV and BV are the ending and beginning values, while n is the number of time periods (usually months or years) 
        for which you are calculating an average. The ^ character means “to the power of”; we take the ratio of EV / BV 
        and raise it to the power of 1/n. Subtracting one (one = 100%)
        """
        return ((end_value / start_value) ** (1 / num_years)) - 1
