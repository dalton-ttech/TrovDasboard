/* Always derive Pacific time from the IANA zone, including daylight saving changes. */
(() => {
  'use strict';
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit',
    weekday: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit',
    hourCycle: 'h23', timeZoneName: 'short',
  });
  const weekdays = { Sun: '周日', Mon: '周一', Tue: '周二', Wed: '周三', Thu: '周四', Fri: '周五', Sat: '周六' };
  function format(now = new Date()) {
    const p = Object.fromEntries(formatter.formatToParts(now).map(part => [part.type, part.value]));
    return {
      date: `${p.year}.${p.month}.${p.day} ${weekdays[p.weekday]}`,
      time: `${p.hour}:${p.minute}:${p.second}`,
      zone: p.timeZoneName,
      iso: now.toISOString(),
    };
  }
  function update(root, now = new Date()) {
    const clock = root.querySelector('[data-pacific-clock]');
    if (!clock) return;
    const value = format(now);
    clock.dateTime = value.iso;
    clock.querySelector('[data-pacific-date]').textContent = value.date;
    clock.querySelector('[data-pacific-time]').textContent = value.time;
    clock.querySelector('[data-pacific-zone]').textContent = `太平洋时间 · ${value.zone}`;
  }
  window.TrovClock = { format, update };
})();
