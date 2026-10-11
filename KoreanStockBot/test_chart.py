import unittest
from app import return_series


class ReturnPeriodTests(unittest.TestCase):
    rows=[{'date':d,'equity':v} for d,v in [
        ('2025-12-31',110),('2026-01-02',121),('2026-02-02',133.1),('2026-02-03',146.41)]]

    def test_period_baselines(self):
        for period,expected in [('전체',46.41),('연',33.1),('월',21),('주',21),('일',10)]:
            with self.subTest(period=period):
                values,dates=return_series(self.rows,100,period)
                self.assertAlmostEqual(values[-1],expected)
                self.assertEqual(values[0],0)
                self.assertEqual(dates[-1],'2026-02-03')

    def test_custom_uses_previous_observation(self):
        values,dates=return_series(self.rows,100,'직접 기간','2026-01-01','2026-01-31')
        self.assertAlmostEqual(values[-1],10)
        self.assertEqual(dates,['2025-12-31','2026-01-02'])

    def test_empty_and_invalid(self):
        self.assertEqual(return_series([],100),([],[]))
        self.assertEqual(return_series(self.rows,100,'직접 기간','2027-01-01','2027-01-02'),([],[]))
        with self.assertRaises(ValueError):
            return_series(self.rows,100,'직접 기간','2026-02-02','2026-01-01')

    def test_first_day_uses_capital(self):
        values,_=return_series(self.rows[:1],100,'일')
        self.assertAlmostEqual(values[-1],10)


if __name__=='__main__': unittest.main()
