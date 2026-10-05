import datetime
from decimal import Decimal
import importlib.util
import math
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'scripts' / 'build_housing_data.py'
spec = importlib.util.spec_from_file_location('pipeline', path)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class PipelineTests(unittest.TestCase):
    def test_roc_dates(self):
        self.assertEqual(p.date_value('1050101'), datetime.date(2016,1,1))
        self.assertEqual(p.date_value('1141231'), datetime.date(2025,12,31))
        self.assertEqual(p.date_value('990101'), datetime.date(2010,1,1))
        self.assertIsNone(p.date_value('1140230'))
        self.assertIsNone(p.date_value('transaction year month and day'))

    def test_exact_area_conversion(self):
        self.assertEqual(p.unit_price_wan_per_ping(121000),Decimal(40))
        self.assertAlmostEqual(float(p.unit_price_wan_per_ping(10000)),400/121)

    def test_medians(self):
        odd = p.aggregate_record('桃園區',2025,'all',[5,1,4,2,3])
        even = p.aggregate_record('桃園區',2025,'all',[6,1,5,2,4,3])
        self.assertEqual(odd['medianPrice'],3)
        self.assertEqual(even['medianPrice'],3.5)

    def test_invalid_numeric_values(self):
        for value in ['',None,'oops','NaN','inf','-inf']:
            self.assertEqual(p.numeric({'x':value},'x'),0)
            self.assertEqual(p.decimal_numeric({'x':value},'x'),Decimal(0))
        self.assertEqual(p.numeric({'x':'123.5'},'x'),123.5)
        self.assertEqual(p.decimal_numeric({'x':'9873798.5'},'x'),Decimal('9873798.5'))

    def test_decimal_midpoint_regression(self):
        totals=['10000','20000','9873798','9873799','10000000','20000000']
        values=[p.decimal_numeric({'total':x},'total')/Decimal(10000) for x in totals]
        cell=p.aggregate_record('桃園市',2020,'townhouse',values)
        self.assertEqual(cell['medianPrice'],987.3798)
        # A five-decimal midpoint must use explicit half-even decimal rounding.
        self.assertEqual(p.aggregate_record('桃園市',2020,'townhouse',[Decimal('987.37985')]*5)['medianPrice'],987.3798)

    def test_small_samples_and_empty(self):
        empty=p.aggregate_record('復興區',2025,'all',[])
        tiny=p.aggregate_record('復興區',2025,'all',[20,30,40,50])
        low=p.aggregate_record('新屋區',2025,'all',list(range(5)))
        large=p.aggregate_record('桃園區',2025,'all',list(range(30)))
        self.assertEqual((empty['medianPrice'],empty['status'],empty['count']),(None,'no_data',0))
        self.assertEqual((tiny['medianPrice'],tiny['status']),(None,'suppressed'))
        self.assertTrue(low['lowSample'])
        self.assertEqual(large['status'],'ok')

    def test_latest_cohort_retained(self):
        data={}
        old={'編號':'id1','單價元平方公尺':'100000'}
        new={'編號':'id1','單價元平方公尺':'110000'}
        self.assertEqual(p.retain_latest(data,old,'114S4'),'new')
        self.assertEqual(p.retain_latest(data,new,'115S1'),'updated')
        p.retain_latest(data,old,'114S3')
        self.assertEqual(data['id1'],(new,'115S1'))
        self.assertEqual(p.retain_latest(data,new,'115S2'),'duplicate')
        self.assertEqual(len(data),1)
        self.assertEqual(p.retain_latest(data,{'編號':''},'115S2'),'missing')

if __name__=='__main__': unittest.main()
