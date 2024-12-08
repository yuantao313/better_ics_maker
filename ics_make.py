from icalendar import Calendar, Event, Alarm
import time
from pytz import UTC
import os
from functools import lru_cache
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class Repeat(Enum):
    ONCE = 0
    DAILY = 1
    WEEKLY = 2
    MONTHLY = 3
    YEARLY = 4


class Holiday(Enum):
    NO_CHANGE = 0
    BEFORE = 1
    AFTER = 2


class Rule:
    def __init__(self, start_time: datetime,
                 repeat: Repeat,
                 repeat_frequency: int,
                 end_time: Optional[datetime] = None,
                 holiday: Holiday = Holiday.NO_CHANGE):
        self.start_time = start_time
        self.repeat = repeat
        self.repeat_frequency = repeat_frequency
        if end_time is None:
            # until the end of the year
            end_time = datetime(year=start_time.year+1, month=1, day=1)
        self.end_time = end_time
        self.holiday = holiday

    @lru_cache
    def load_holiday_data(self, year: int) -> dict:
        if not os.path.exists(f"holidays_api/data/{year}_data.json"):
            print("data not exist")
        with open(f"holidays_api/data/{year}_data.json", "r", encoding="utf-8") as holiday_data:
            return json.load(holiday_data)

    def check_if_chinese_holiday(self, date: datetime) -> bool:
        year = date.year

        holiday_data_json = self.load_holiday_data(year)
        month_day_key = f"{date.month:02d}{date.day:02d}"
        if month_day_key in holiday_data_json:
            return holiday_data_json[month_day_key] != 0
        else:
            return date.weekday() in [5, 6]

    def check_if_huawei_workday(self, date: datetime) -> bool:
        # 月末周六
        if not date.weekday == 5:
            return False
        # 是否是月末周六
        if (date+timedelta(weeks=1)).month == date.month:
            return False

        # 当该天设置为工作日时，是否出现连续工作超过七天的情况
        # 两边搜索
        # 前边
        work_before = 0
        date_ptr = date
        while True:
            date_ptr -= timedelta(days=1)
            if not self.check_if_chinese_holiday(date_ptr):
                work_before += 1
            else:
                break
        work_after = 0
        date_ptr = date
        while True:
            date_ptr += timedelta(days=1)
            if not self.check_if_chinese_holiday(date_ptr):
                work_after += 1
            else:
                break
        if work_before + work_after + 1 >= 7:
            return False
        return True

    def check_if_holiday(self, date: datetime) -> bool:
        if self.check_if_huawei_workday(date):
            return False
        return self.check_if_chinese_holiday(date)

    def make_datetime_list(self) -> list[datetime]:
        result = []
        result.append(self.start_time)
        if self.repeat == Repeat.ONCE:
            return result
        now = self.start_time
        while True:

            if self.repeat == Repeat.DAILY:
                now += timedelta(days=self.repeat_frequency)
            elif self.repeat == Repeat.WEEKLY:
                now = datetime(year=now.year, month=now.month,
                               day=now.day+self.repeat_frequency)
            elif self.repeat == Repeat.MONTHLY:
                new_month = now.month+self.repeat_frequency
                if new_month > 12:
                    new_month -= 12
                    now = datetime(year=now.year+1,
                                   month=new_month, day=now.day)
                else:
                    now = datetime(year=now.year, month=new_month, day=now.day)
            next_day = now
            if self.holiday == Holiday.BEFORE:
                while self.check_if_holiday(next_day):
                    next_day -= timedelta(days=1)
            elif self.holiday == Holiday.AFTER:
                while self.check_if_holiday(next_day):
                    next_day += timedelta(days=1)
            if next_day < self.end_time:
                result.append(next_day)
            else:
                break
        return result


def make_event(date: datetime, title: str) -> Event:
    event = Event()
    # 当前时间
    # 时间戳
    # event.add('dtstamp', int(date.timestamp()))
    # 开始时间
    event.add('dtstart', date)
    event.add('X-ALLDAY', 1)
    # 事件名
    event.add('summary', title)
    event.add('description', title)
    tmp_t = time.strftime("%Y%m%d%H%M", time.localtime())
    event['uid'] = tmp_t+'@SWM'

    # freq_of_recurrence = 'DAILY'
    # event.add('rrule', { 'FREQ': freq_of_recurrence, 'INTERVAL': 2})
    return event


if __name__ == "__main__":
    year_now = datetime.now().year
    year_now_new_year_day = datetime(year=year_now, month=1, day=1)
    cal = Calendar()
    cal.add('version', '2.0')
    cal.add('prodid', '-//SWM\'s Calendar//SWM//CN')
    # 推算发工资日期
    for i in Rule(datetime(year=year_now, month=1, day=15), Repeat.MONTHLY, 1, holiday=Holiday.BEFORE).make_datetime_list():
        cal.add_component(make_event(i, '发工资'))
    f = open('example.ics', 'wb')
    f.write(cal.to_ical())
    f.close()
