var calendar;
var currentUser = null;

// 手機斷點：跟 calendar.css 的 @media (max-width: 768px) 保持一致
function isMobileViewport() {
    return window.matchMedia('(max-width: 768px)').matches;
}

// 單日檢視一律用場地格狀（三個場地＝三欄，手機寬度放得下），這樣一眼就能看出
// 哪個場地有課、幾點有課、是哪位教練，也方便直接截圖給教練看當天的課表。
// 單週檢視在手機上維持清單：7 天 × 3 場地 = 21 欄，格狀在手機上只會被壓到
// 完全看不清楚，只能橫向捲動。
function dayViewName() {
    return 'resourceTimeGridDay';
}

function weekViewName() {
    return isMobileViewport() ? 'listWeek' : 'resourceTimeGridWeek';
}

const locNames = {
    'court_out_1': '室外場 1',
    'court_out_2': '室外場 2',
    'court_in': '室內場'
};

// 用「YYYY-MM-DD」字串（date input 的 value）算出星期幾，不透過 new Date(dateStr)
// 那種會被當成 UTC 解析的寫法——雖然台灣是 UTC+8 這裡不會真的跨日，但沿用專案裡
// 其他地方（toLocalDateStr/getMonday）已經在用的「拆解年月日組本地時間」寫法比較保險。
const WEEKDAY_CHARS = ['日', '一', '二', '三', '四', '五', '六'];

function weekdayChar(date) {
    return WEEKDAY_CHARS[date.getDay()];
}

function weekdayLabel(dateStr) {
    if (!dateStr) return '';
    const [y, m, d] = dateStr.split('-').map(Number);
    if (!y || !m || !d) return '';
    return `（週${weekdayChar(new Date(y, m - 1, d))}）`;
}

// 上方導覽列的日期文字。FullCalendar 內建的 view.title 不帶星期，這裡自己組：
// 單日檢視 →「2026年9月5日（週六）」；週檢視 →「2026年8月31日（一）– 9月6日（日）」
function currentDateLabelText(dateInfo) {
    const t = dateInfo.view.type;
    const isDay = t === 'resourceTimeGridDay' || t === 'listDay';
    const start = dateInfo.start;

    if (isDay) {
        return `${start.getFullYear()}年${start.getMonth() + 1}月${start.getDate()}日（週${weekdayChar(start)}）`;
    }

    // dateInfo.end 是「不含」的結束時間（下週一 00:00），往回推一天才是這週最後一天
    const last = new Date(dateInfo.end);
    last.setDate(last.getDate() - 1);

    const head = `${start.getFullYear()}年${start.getMonth() + 1}月${start.getDate()}日（${weekdayChar(start)}）`;
    // 同一年就不重複寫年份，跨年時才補上，避免標籤過長
    const tail = start.getFullYear() === last.getFullYear()
        ? `${last.getMonth() + 1}月${last.getDate()}日（${weekdayChar(last)}）`
        : `${last.getFullYear()}年${last.getMonth() + 1}月${last.getDate()}日（${weekdayChar(last)}）`;
    return `${head} – ${tail}`;
}

// 教練姓名在課表上只顯示姓氏（例如「王教練」→「王」），不重複寫出「教練」二字
function coachSurname(name) {
    if (!name) return name;
    const idx = name.indexOf('教練');
    return idx > 0 ? name.slice(0, idx) : name;
}

// 請假資訊面板只給小編/教練看：學生只會看到自己的課，對其他人的請假狀態沒有意義，
// 而且該角色的 /api/courses 回傳其他學生的課程都是遮蔽過的假資料，湊不出正確名單。
function canViewLeaveInfo() {
    return !!currentUser && (currentUser.role === 'admin' || currentUser.role === 'coach');
}

// 依目前檢視（日/週）決定面板標題文字
function leaveInfoScopeLabel() {
    if (!calendar) return '請假紀錄';
    const t = calendar.view.type;
    const isDay = t === 'resourceTimeGridDay' || t === 'listDay';
    return (isDay ? '本日' : '本週') + '請假紀錄';
}

// 純文字插進 innerHTML 前先跳脫，公告內容是小編自行輸入的文字，避免帶到 HTML 特殊字元
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
}

// 「通知」面板的統一未讀數 = 公告則數 + 自動請假名單筆數，兩邊資料各自非同步
// 更新，所以各自記著自己的數量，變動時都呼叫這個函式重算徽章
let leaveEntryCount = 0;
let notificationCount = 0;
function updateNotificationBadge() {
    const badge = document.getElementById('leaveInfoCount');
    if (!badge) return;
    const total = leaveEntryCount + notificationCount;
    if (total > 0) {
        badge.textContent = total;
        badge.classList.remove('hidden');
    } else {
        badge.classList.add('hidden');
    }
}

// 把目前檢視範圍抓到的課程資料（events 回呼拿到的原始 API 資料）整理成請假名單，
// 用 booking 層級的 status 而非課程層級，這樣同一堂課裡只有部分學生請假時也能準確列出
function renderLeaveInfoPanel(courses) {
    const wrap = document.getElementById('leaveInfoWrap');
    const scopeLabel = document.getElementById('leaveInfoScopeLabel');
    const list = document.getElementById('leaveInfoList');
    if (!wrap || !list) return;

    if (!canViewLeaveInfo()) {
        wrap.classList.add('hidden');
        return;
    }
    wrap.classList.remove('hidden');
    if (scopeLabel) scopeLabel.textContent = leaveInfoScopeLabel();

    const entries = [];
    (courses || []).forEach(c => {
        (c.students || []).forEach(s => {
            if (s.status === 'leave_requested' || s.status === 'leave_approved') {
                entries.push({
                    studentName: s.name,
                    approved: s.status === 'leave_approved',
                    startTime: c.start_time,
                    location: locNames[c.location] || c.location || '',
                    coach: coachSurname(c.coach_name)
                });
            }
        });
    });
    entries.sort((a, b) => new Date(a.startTime) - new Date(b.startTime));

    leaveEntryCount = entries.length;
    updateNotificationBadge();

    if (entries.length === 0) {
        list.innerHTML = '<div class="text-xs text-slate-400 text-center py-4">目前檢視範圍內沒有請假紀錄</div>';
        return;
    }

    list.innerHTML = entries.map(e => {
        const dt = new Date(e.startTime);
        const dtStr = dt.toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', weekday: 'short', hour: '2-digit', minute: '2-digit' });
        const statusClass = e.approved ? 'bg-slate-200 text-slate-600' : 'bg-amber-100 text-amber-700';
        const statusText = e.approved ? '已請假' : '待審核';
        return `
            <div class="p-2 rounded-lg border border-slate-100 bg-slate-50/60">
                <div class="flex items-center justify-between gap-2">
                    <span class="text-xs font-bold text-slate-800 truncate">${escapeHtml(e.studentName)}</span>
                    <span class="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 ${statusClass}">${statusText}</span>
                </div>
                <div class="text-[11px] text-slate-500 mt-0.5">${dtStr} · ${e.location} · ${escapeHtml(e.coach)}教練</div>
            </div>
        `;
    }).join('');
}

// 小編自行新增的公告（教練請假、貴賓來訪等），跟自動產生的請假名單不同來源，
// 不綁日期/週次，小編何時想刪就刪，教練只能看不能新增/刪除
function renderNotifications(notifications) {
    const container = document.getElementById('notificationList');
    const addRow = document.getElementById('addNotificationRow');
    if (!container) return;

    const canManage = !!currentUser && currentUser.role === 'admin';
    if (addRow) {
        addRow.classList.toggle('hidden', !canManage);
        addRow.classList.toggle('flex', canManage);
    }

    if (!notifications || notifications.length === 0) {
        container.innerHTML = '<div class="text-xs text-slate-400 text-center py-2">目前沒有公告</div>';
        return;
    }

    container.innerHTML = notifications.map(n => `
        <div class="flex items-start justify-between gap-2 p-2 rounded-lg border border-blue-100 bg-blue-50/60">
            <span class="text-xs text-slate-700 flex-1 break-words">${escapeHtml(n.message)}</span>
            ${canManage ? `<button type="button" class="delete-notification-btn text-slate-400 hover:text-rose-600 shrink-0 text-xs leading-4" data-id="${n.id}">✕</button>` : ''}
        </div>
    `).join('');
}

function fetchNotifications() {
    if (!canViewLeaveInfo()) return;
    authFetch('/api/notifications')
        .then(res => res.json())
        .then(data => {
            notificationCount = Array.isArray(data) ? data.length : 0;
            updateNotificationBadge();
            renderNotifications(data);
        })
        .catch(err => console.error('Error fetching notifications:', err));
}

function initLeaveInfoPanel() {
    const btn = document.getElementById('leaveInfoBtn');
    const panel = document.getElementById('leaveInfoPanel');
    const wrap = document.getElementById('leaveInfoWrap');
    if (!btn || !panel || !wrap) return;

    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        panel.classList.toggle('hidden');
    });

    document.addEventListener('click', function(e) {
        if (!wrap.contains(e.target)) panel.classList.add('hidden');
    });
}

function initNotifications() {
    const addBtn = document.getElementById('addNotificationBtn');
    const input = document.getElementById('notificationInput');
    const list = document.getElementById('notificationList');

    if (addBtn && input) {
        const submitNotification = function() {
            const message = input.value.trim();
            if (!message) return;
            addBtn.disabled = true;
            authFetch('/api/notifications', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            })
            .then(async res => {
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || '新增通知失敗');
                input.value = '';
                fetchNotifications();
            })
            .catch(err => alert('新增通知發生錯誤：' + err.message))
            .finally(() => { addBtn.disabled = false; });
        };
        addBtn.addEventListener('click', submitNotification);
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitNotification();
            }
        });
    }

    if (list) {
        list.addEventListener('click', function(e) {
            const btn = e.target.closest('.delete-notification-btn');
            if (!btn) return;
            if (!confirm('確定刪除這則通知？')) return;
            authFetch(`/api/notifications/${btn.getAttribute('data-id')}`, { method: 'DELETE' })
                .then(async res => {
                    const body = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(body.error || '刪除通知失敗');
                    fetchNotifications();
                })
                .catch(err => alert('刪除通知發生錯誤：' + err.message));
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // 檢查登入使用者
    const userStr = localStorage.getItem('kol_user');
    if (userStr) {
        try {
            currentUser = JSON.parse(userStr);
        } catch(e) {}
    }

    var calendarEl = document.getElementById('calendar');
    const isAdmin = !!currentUser && currentUser.role === 'admin';

    calendar = new FullCalendar.Calendar(calendarEl, {
        locale: 'zh-tw',
        initialView: isMobileViewport() ? dayViewName() : 'resourceTimeGridWeek',
        datesAboveResources: true,
        
        resources: [
            { id: 'court_out_1', title: '室外場 1' },
            { id: 'court_out_2', title: '室外場 2' },
            { id: 'court_in', title: '室內場' }
        ],

        // 一週從星期一開始。系統其他地方全是以星期一為一週之始（固定課表的
        // day_of_week 0=星期一、套用課表也是傳週一的日期），但 FullCalendar
        // 預設從星期日起算，導致週檢視顯示 8/23–8/29、上方週次選單卻顯示
        // 8/24~8/30，兩者差一週，跳週時看起來像沒有跟著動。
        firstDay: 1,

        slotMinTime: '07:00:00',
        slotMaxTime: '22:00:00',
        // 手機上把格線改成每小時一條（桌機維持半小時）。7:00~22:00 用半小時格
        // 是 30 列，手機高度根本塞不下，只能捲動；改成每小時一條就剩 15 列，
        // 整天剛好一個畫面看完。課程方塊是依實際時間定位的，不是對齊格線，
        // 所以 10:30 這種半點開始的課位置照樣正確，只是背景格線變成整點。
        slotDuration: isMobileViewport() ? '01:00:00' : '00:30:00',

        allDaySlot: false,
        headerToolbar: false,
        stickyHeaderDates: true,
        // 讓時間列撐滿容器高度：手機改成每小時一格（15 列）後，剛好能填滿而不
        // 溢出，課程方塊也才有足夠高度顯示「學生 + 教練」兩行。
        // （之前手機關掉這個選項，是因為半小時格有 24 列時 expandRows 算出來的
        //   列高會超出容器約 20px，反而擠出內部捲軸。）
        expandRows: true,

        // 每個場地欄至少 90px，欄位塞不下時由 FullCalendar 自己的 scrollgrid 產生
        // 橫向捲軸——這樣左側時間欄會被固定住，往右捲看後面幾天時仍然對得到時間。
        // （以前是用 CSS 的 #calendar{min-width:1800px} 撐寬、讓外層容器橫向捲動，
        //   但那會連時間欄一起捲出畫面，右邊的課就看不出是幾點的課。）
        // 單週 7 天 × 3 場地 = 21 欄，90px × 21 ≈ 1890px，跟原本 1800px 差不多寬；
        // 螢幕夠寬時欄位會自動撐開填滿，不會硬留捲軸。
        dayMinWidth: 90,

        selectable: isAdmin, // 僅 Admin 可點選排課
        editable: isAdmin,   // 僅 Admin 支援直接拖曳調課 (Drag & Drop)
        selectMirror: true,
        noEventsText: '這天沒有排課',

        // listDay 檢視預設的日期標題只顯示星期幾（例如「星期六」），完全不帶
        // 日期數字——FullCalendar 假設頁面上的標題列會另外顯示完整日期，但
        // 這個系統的標題列是自訂的（headerToolbar: false），沒有任何地方顯示
        // 日期，導致手機版切日期時每天看起來都一樣，完全看不出是幾號。這裡把
        // listDayFormat 固定成「星期幾 + 完整日期」，listWeek 的每列本來就有
        // side text 帶日期，一起蓋掉讓兩種清單檢視顯示格式一致。
        listDayFormat: { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' },
        listDaySideFormat: false,

        // 跨越手機/桌機斷點時，把目前「日或週」的意圖對應到該斷點該用的檢視
        // （單週在手機上是清單、其餘都是場地格狀）。只在真的需要換檢視時才切，
        // 避免使用者在同一斷點內縮放視窗時被打斷。
        windowResize: function(arg) {
            // windowResize 的參數是 { view } 包裝物件，不是 View 本身——直接讀
            // arg.type 會是 undefined，讓下面的判斷整段失效（呼叫端在斷點切換
            // 時完全沒反應），要透過 arg.view.type 才拿得到目前的檢視名稱。
            const viewType = arg.view.type;
            const isWeek = viewType === 'listWeek' || viewType === 'resourceTimeGridWeek';
            const want = isWeek ? weekViewName() : dayViewName();
            calendar.setOption('slotDuration', isMobileViewport() ? '01:00:00' : '00:30:00');
            if (viewType !== want) calendar.changeView(want);
        },

        // 拖曳調課事件處理 (Drag & Drop)
        eventDrop: function(info) {
            const courseId = info.event.id;
            const newStart = info.event.start;
            const newEnd = info.event.end;
            const newLocation = info.event.getResources()[0] ? info.event.getResources()[0].id : 'court_out_1';

            if (!confirm(`確定將此課程調移至：\n時段：${newStart.toLocaleString('zh-TW')}\n場地：${newLocation}？`)) {
                info.revert();
                return;
            }

            authFetch(`/api/courses/${courseId}/reschedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_time: newStart.toISOString(),
                    end_time: newEnd.toISOString(),
                    location: newLocation
                })
            })
            .then(async res => {
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || '調課失敗');
                return body;
            })
            .then(() => {
                calendar.refetchEvents();
            })
            .catch(err => {
                alert('調課失敗：' + err.message);
                info.revert();
            });
        },

        // 拖曳調整課程長度 (Resize) — editable:true 預設也會開放拖曳邊緣調整時長，
        // 若不接這個 callback，畫面上看起來調整成功，但其實沒送到後端，重新整理/切換
        // 週次後會整個復原，小編完全不會發現。這裡直接沿用跟 eventDrop 一樣的邏輯。
        eventResize: function(info) {
            const courseId = info.event.id;
            const newStart = info.event.start;
            const newEnd = info.event.end;

            if (!confirm(`確定調整此課程時長為：\n${newStart.toLocaleString('zh-TW')} ~ ${newEnd.toLocaleTimeString('zh-TW')}？`)) {
                info.revert();
                return;
            }

            authFetch(`/api/courses/${courseId}/reschedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_time: newStart.toISOString(),
                    end_time: newEnd.toISOString()
                })
            })
            .then(async res => {
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || '調整時長失敗');
                return body;
            })
            .then(() => {
                calendar.refetchEvents();
            })
            .catch(err => {
                alert('調整時長失敗：' + err.message);
                info.revert();
            });
        },

        // 渲染課程方塊內容：換行顯示 {學生} \n {程度} \n {教練}
        eventContent: function(arg) {
            let coach = arg.event.extendedProps.coach_name || '';
            let level = arg.event.extendedProps.level || '';
            let student = arg.event.title || '無姓名';
            let isTrial = arg.event.extendedProps.is_trial;
            let trialFee = arg.event.extendedProps.trial_fee;
            let status = arg.event.extendedProps.status;
            let isOtherStudent = arg.event.extendedProps.is_other_student;
            let isUnassigned = arg.event.extendedProps.is_unassigned;
            let location = locNames[arg.event.extendedProps.location] || arg.event.extendedProps.location || '';
            let isListView = arg.view.type.startsWith('list');

            if (isOtherStudent) {
                let coachColor = arg.event.extendedProps.coach_color || '#3b82f6';
                if (isListView) {
                    return {
                        html: `<span class="coach-name-text px-2 py-0.5 rounded-md text-xs font-bold border" style="background-color: ${coachColor}15; color: ${coachColor}; border-color: ${coachColor};">${coach}${location ? ' · ' + location : ''}</span>`
                    };
                }
                return {
                    html: `
                        <div class="w-full h-full p-1 flex items-center justify-center">
                            <span class="coach-name-text px-2 py-0.5 rounded-md text-[11px] font-bold border" style="background-color: ${coachColor}15; color: ${coachColor}; border-color: ${coachColor};">
                                ${coach}
                            </span>
                        </div>
                    `
                };
            }

            let leaveBadgeClass = isListView ? 'bg-slate-500 text-white' : 'bg-black/50 text-white';
            let leaveBadge = (status === 'cancelled') ? `<span class="text-[10px] ${leaveBadgeClass} px-1.5 py-0.5 rounded font-normal">已請假</span>` : '';
            let leaveReqBadge = (arg.event.extendedProps.leave_status === 'requested') ? '<span class="text-[10px] bg-amber-500 text-white px-1.5 py-0.5 rounded font-bold">請假待審</span>' : '';
            let unassignedBadge = isUnassigned ? '<span class="text-[10px] bg-slate-800 text-white px-1.5 py-0.5 rounded font-bold">待排課</span>' : '';
            let trialBadge = isTrial ? `<span class="text-[10px] bg-amber-500 text-white font-bold px-1.5 py-0.5 rounded">體驗${trialFee ? '$' + trialFee : ''}</span>` : '';
            let completedBadge = (status === 'completed') ? '<span class="text-[10px] bg-emerald-600 text-white px-1.5 py-0.5 rounded font-normal">已簽到</span>' : '';

            // 手機的單日/單週清單檢視：時間已由 FullCalendar 內建欄位顯示，這裡把場地/學生/
            // 教練/程度/狀態排成一行式卡片，方便直向捲動時一眼看清單日詳細排課情形。
            if (isListView) {
                let coachColor = arg.event.extendedProps.coach_color || '#64748b';
                return {
                    html: `
                        <div class="w-full py-1 flex flex-wrap items-center gap-x-2 gap-y-1 cursor-pointer">
                            <span class="text-xs font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">${location}</span>
                            <span class="font-bold text-sm text-slate-800">${student}</span>
                            ${level ? `<span class="text-xs text-slate-400">（${level}）</span>` : ''}
                            <span class="coach-name-text text-xs font-medium px-1.5 py-0.5 rounded" style="background-color:${coachColor}15; color:${coachColor};">${coach || '待排'}</span>
                            ${unassignedBadge}${leaveBadge}${leaveReqBadge}${completedBadge}${trialBadge}
                        </div>
                    `
                };
            }

            let levelDiv = level ? `<div class="text-[11px] font-normal opacity-90 leading-tight break-words">${level}</div>` : '';
            let coachDiv = `<div class="coach-name-text text-[11px] ${isUnassigned ? 'text-slate-200 italic' : 'font-medium opacity-95'} leading-tight break-words">${coach || '待排'}</div>`;

            return {
                html: `
                    <div class="w-full h-full cursor-pointer hover:opacity-95 transition-opacity p-1 text-white flex flex-col justify-start text-left overflow-hidden">
                        <div class="font-bold text-[12px] leading-tight break-words">${student}</div>
                        ${levelDiv}
                        ${coachDiv}
                        <div class="flex flex-col gap-0.5 mt-0.5">
                            ${unassignedBadge}
                            ${leaveBadge}
                            ${leaveReqBadge}
                            ${completedBadge}
                            ${trialBadge}
                        </div>
                    </div>
                `
            };
        },

        // 點擊新增課程 (小編/Admin 專屬)
        select: function(info) {
            if (!isAdmin) {
                alert('僅小編或蔡教練(Admin)具備排課權限。');
                calendar.unselect();
                return;
            }
            openCourseModal(info);
        },

        // 點擊既有課程進入編輯/請假模式
        eventClick: function(info) {
            const e = info.event;
            if (e.extendedProps.is_other_student) {
                alert(`此時段為 ${e.extendedProps.coach_name} 教練的授課時段（已有學員預約）。`);
                return;
            }

            if (currentUser && currentUser.role === 'coach') {
                let msg = `課程名稱：${e.title}\n時間：${e.start.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} ~ ${e.end.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}\n教練：${e.extendedProps.coach_name}`;
                if (e.extendedProps.is_trial) {
                    msg += `\n【體驗課提醒】人數: ${e.extendedProps.trial_count || 1} 人，需收費: $${e.extendedProps.trial_fee || 0} 元`;
                }
                alert(msg);
                return;
            }

            if (currentUser && currentUser.role === 'student') {
                if (e.extendedProps.leave_status === 'requested') {
                    if (confirm(`【請假審核中】此課程正在等待小編審核中。\n\n是否要撤回請假申請？`)) {
                        authFetch(`/api/courses/${e.id}/withdraw-leave`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ user_id: currentUser.id })
                        })
                        .then(res => res.json())
                        .then(d => {
                            alert(d.message);
                            calendar.refetchEvents();
                        });
                    }
                } else if (e.extendedProps.status === 'cancelled' || e.extendedProps.leave_status === 'approved') {
                    alert('此課程已完成請假審核，時段已釋出。');
                } else {
                    let reason = prompt(`【申請請假】課程：${e.title}\n時間：${e.start.toLocaleString('zh-TW')}\n\n請輸入請假原因（送出後待小編審核）：`, '臨時有事請假');
                    if (reason !== null) {
                        authFetch(`/api/courses/${e.id}/request-leave`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                user_id: currentUser.id,
                                reason: reason
                            })
                        })
                        .then(res => res.json())
                        .then(d => {
                            alert(d.message);
                            calendar.refetchEvents();
                        });
                    }
                }
                return;
            }

            openEditCourseModal(info.event);
        },

        // 取得資料庫數據 (含學生隱私過濾與教練過濾)
        events: function(fetchInfo, successCallback, failureCallback) {
            let startStr = fetchInfo.startStr;
            let endStr = fetchInfo.endStr;
            let url = `/api/courses?start_date=${encodeURIComponent(startStr)}&end_date=${encodeURIComponent(endStr)}`;
            
            if (currentUser) {
                url += `&user_role=${currentUser.role}`;
                if (currentUser.role === 'coach') {
                    url += `&coach_id=${currentUser.id}`;
                } else if (currentUser.role === 'student') {
                    url += `&student_id=${currentUser.id}`;
                }
            }

            authFetch(url)
                .then(response => response.json())
                .then(data => {
                    // 教練勾選篩選（小編專用，可複選）。在前端過濾而不是打回後端，
                    // 是因為後端的 coach_id 參數一次只吃一位教練，複選需要自己過濾。
                    let scoped = applyCoachFilter(data);

                    renderLeaveInfoPanel(scoped);

                    // 已核准請假 (status=cancelled) 的課不再佔用課表格子——請假名單已經
                    // 有「請假資訊」面板可以查，格子留著灰色方塊只會讓小編以為時段還被佔用，
                    // 排不了別的課。只對看得到請假面板的小編/教練套用；學生沒有面板可查，
                    // 還是讓他們在自己的課表上看得到「這堂已經請假」的紀錄。
                    let visibleCourses = canViewLeaveInfo()
                        ? scoped.filter(course => course.status !== 'cancelled')
                        : scoped;

                    let mappedEvents = visibleCourses.map(course => {
                        let title = course.title || (course.students && course.students.length > 0 
                            ? course.students.map(s => s.name).join(', ') 
                            : '未命名課程');
                        
                        let status = course.status || 'scheduled';
                        
                        let bgColor = '#64748b'; // 預設灰階 (尚未排課/待排教練)
                        let borderColor = '#475569';
                        let coachDisplayName = coachSurname(course.coach_name);

                        if (course.is_other_student) {
                            bgColor = '#ffffff';
                            borderColor = '#e2e8f0';
                        } else if (status === 'cancelled') {
                            bgColor = '#9ca3af'; // 灰色置頂 (請假)
                            borderColor = '#9ca3af';
                        } else if (course.coach_color) {
                            bgColor = course.coach_color;
                            borderColor = course.coach_color;
                        } else {
                            coachDisplayName = '待排';
                        }

                        return {
                            id: course.course_id,
                            resourceId: course.location,
                            title: title,
                            start: course.start_time,
                            end: course.end_time,
                            backgroundColor: bgColor,
                            borderColor: borderColor,
                            extendedProps: {
                                coach_name: coachDisplayName,
                                coach_id: course.coach_id,
                                coach_color: course.coach_color || '#64748b',
                                status: status,
                                is_unassigned: !course.coach_id,
                                leave_status: course.leave_status || 'none',
                                level: course.description || '',
                                is_trial: course.is_trial,
                                trial_count: course.trial_count,
                                trial_fee: course.trial_fee,
                                is_other_student: course.is_other_student || false,
                                is_recurring: course.is_recurring || false,
                                location: course.location
                            }
                        };
                    });
                    successCallback(mappedEvents);
                })
                .catch(err => {
                    console.error('Error fetching courses:', err);
                    failureCallback(err);
                });
        },

        datesSet: function(dateInfo) {
            updateWeekSelector(dateInfo.start);
            // headerToolbar:false 拿掉了 FullCalendar 自己的標題列，list 檢視
            // 「這天沒有排課」的空狀態又完全不帶日期（見 listDayFormat 的註解），
            // 所以自訂標頭需要自己補一個永遠看得到的日期/週期文字，不管切到哪個
            // 檢視、當天有沒有課都看得出現在是幾號。
            const label = document.getElementById('currentDateLabel');
            if (label) label.textContent = currentDateLabelText(dateInfo);
        }
    });

    calendar.render();

    // 手機預設是單日清單檢視，把 日/週 切換鈕的樣式同步成「日」被選取，
    // 不然按鈕看起來停在「週」但實際渲染的是單日清單，會讓人誤會。
    if (isMobileViewport()) {
        const dayBtnEl = document.getElementById('viewDayBtn');
        const weekBtnEl = document.getElementById('viewWeekBtn');
        if (dayBtnEl && weekBtnEl) {
            dayBtnEl.className = "px-3 py-1 rounded-md bg-white shadow-sm text-blue-600 font-bold transition-all";
            weekBtnEl.className = "px-3 py-1 rounded-md text-slate-600 font-medium hover:text-slate-900 transition-all";
        }
    }

    flatpickr("#mini-calendar", {
        inline: true,
        // 跟主課表一樣以星期一為一週之始，避免側邊小日曆和右側週檢視的
        // 星期欄位對不起來，看日期時更容易誤判
        locale: { ...flatpickr.l10ns.zh_tw, firstDayOfWeek: 1 },
        onChange: function(selectedDates) {
            if (selectedDates.length > 0) {
                calendar.gotoDate(selectedDates[0]);
            }
        }
    });
    
    initModalEvents();
    fetchCoaches();
    fetchStudentsForForm();
    initWeekSelector();
    initViewToggle();
    initTrialToggles();
    initLeaveInfoPanel();
    initNotifications();
    fetchNotifications();
    initCoachFilter();
});

// ============================================================
// 體驗課欄位切換
// ============================================================
function initTrialToggles() {
    const isTrialCheck = document.getElementById('isTrial');
    const trialFields = document.getElementById('trialFields');
    const isRecurringCheck = document.getElementById('isRecurring');
    if (isTrialCheck && trialFields) {
        isTrialCheck.addEventListener('change', function() {
            trialFields.classList.toggle('hidden', !this.checked);
            // 體驗課是單次性質，不應該變成常態固定課程
            if (isRecurringCheck) {
                isRecurringCheck.disabled = this.checked;
                if (this.checked) isRecurringCheck.checked = false;
            }
        });
    }

    const editIsTrialCheck = document.getElementById('editIsTrial');
    const editTrialFields = document.getElementById('editTrialFields');
    const editIsRecurringCheck = document.getElementById('editIsRecurring');
    if (editIsTrialCheck && editTrialFields) {
        editIsTrialCheck.addEventListener('change', function() {
            editTrialFields.classList.toggle('hidden', !this.checked);
            if (editIsRecurringCheck) {
                editIsRecurringCheck.disabled = this.checked;
                if (this.checked) editIsRecurringCheck.checked = false;
            }
        });
    }
}

// ============================================================
// 學生列表 (連動資料庫，用於新增課程時綁定 student_id)
// ============================================================
var studentNameToId = {};

function fetchStudentsForForm() {
    authFetch('/api/users/students')
        .then(response => response.json())
        .then(data => {
            studentNameToId = {};
            const datalist = document.getElementById('studentDatalist');
            if (datalist) datalist.innerHTML = '';
            data.forEach(student => {
                studentNameToId[student.display_name] = student.id;
                if (datalist) {
                    const option = document.createElement('option');
                    option.value = student.display_name;
                    datalist.appendChild(option);
                }
            });
        })
        .catch(err => console.error('Error fetching students:', err));
}

// ============================================================
// 教練列表
// ============================================================
function fetchCoaches() {
    authFetch('/api/users/coaches')
        .then(response => response.json())
        .then(data => {
            const coachSelect = document.getElementById('coachName');
            const editCoachSelect = document.getElementById('editCoachName');
            if (coachSelect) coachSelect.innerHTML = '<option value="">未指定 (待排教練 / 灰階色)</option>';
            if (editCoachSelect) editCoachSelect.innerHTML = '<option value="">未指定 (待排教練 / 灰階色)</option>';
            if (coachSelect) coachSelect.value = '';
            if (editCoachSelect) editCoachSelect.value = '';
            
            data.forEach(coach => {
                const option = document.createElement('option');
                option.value = coach.id;
                option.textContent = coach.display_name;
                if (coachSelect) coachSelect.appendChild(option);

                if (editCoachSelect) {
                    const editOption = option.cloneNode(true);
                    editCoachSelect.appendChild(editOption);
                }
            });

            renderCoachFilterOptions(data);
        })
        .catch(err => console.error('Error fetching coaches:', err));
}

// ============================================================
// 教練勾選篩選 (小編專用，可複選)
// ============================================================
// null = 尚未載入教練清單／不篩選；Set = 目前勾選的 coach_id（'' 代表待排教練的課）
var selectedCoachIds = null;

function renderCoachFilterOptions(coaches) {
    const container = document.getElementById('coachFilterOptions');
    if (!container) return;

    // 預設全勾（＝顯示全部），重新載入教練清單時保留使用者已經取消勾選的狀態
    const prev = selectedCoachIds;
    selectedCoachIds = new Set();
    coaches.forEach(c => {
        if (!prev || prev.has(c.id)) selectedCoachIds.add(c.id);
    });
    if (!prev || prev.has('')) selectedCoachIds.add('');

    container.innerHTML = coaches.map(c => `
        <label class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 cursor-pointer">
            <input type="checkbox" class="coach-filter-item rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5" value="${c.id}" ${selectedCoachIds.has(c.id) ? 'checked' : ''}>
            <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background-color:${c.color || '#64748b'};"></span>
            <span class="text-xs text-slate-700">${escapeHtml(c.display_name)}</span>
        </label>
    `).join('') + `
        <label class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 cursor-pointer">
            <input type="checkbox" class="coach-filter-item rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5" value="" ${selectedCoachIds.has('') ? 'checked' : ''}>
            <span class="w-2.5 h-2.5 rounded-full shrink-0 bg-slate-500"></span>
            <span class="text-xs text-slate-700">待排教練</span>
        </label>
    `;

    updateCoachFilterLabel();
}

// 依目前勾選狀況過濾課程資料；全勾或還沒載入清單時原樣回傳
function applyCoachFilter(courses) {
    if (!selectedCoachIds) return courses;
    const boxes = document.querySelectorAll('.coach-filter-item');
    if (boxes.length === 0) return courses;
    if (selectedCoachIds.size === boxes.length) return courses;
    return courses.filter(c => selectedCoachIds.has(c.coach_id || ''));
}

function updateCoachFilterLabel() {
    const label = document.getElementById('coachFilterLabel');
    const allBox = document.getElementById('coachFilterAll');
    const boxes = document.querySelectorAll('.coach-filter-item');
    if (!label) return;

    const total = boxes.length;
    const picked = selectedCoachIds ? selectedCoachIds.size : total;

    if (allBox) allBox.checked = total > 0 && picked === total;

    if (total === 0 || picked === total) {
        label.textContent = '全部教練';
    } else if (picked === 0) {
        label.textContent = '未選教練';
    } else if (picked === 1) {
        const only = Array.from(boxes).find(b => b.checked);
        label.textContent = only ? only.closest('label').innerText.trim() : `${picked} 位教練`;
    } else {
        label.textContent = `${picked} 位教練`;
    }
}

function initCoachFilter() {
    const wrap = document.getElementById('coachFilterWrap');
    const btn = document.getElementById('coachFilterBtn');
    const panel = document.getElementById('coachFilterPanel');
    const allBox = document.getElementById('coachFilterAll');
    const options = document.getElementById('coachFilterOptions');
    if (!wrap || !btn || !panel) return;

    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        panel.classList.toggle('hidden');
    });
    document.addEventListener('click', function(e) {
        if (!wrap.contains(e.target)) panel.classList.add('hidden');
    });

    if (allBox) {
        allBox.addEventListener('change', function() {
            const boxes = document.querySelectorAll('.coach-filter-item');
            selectedCoachIds = new Set();
            boxes.forEach(b => {
                b.checked = allBox.checked;
                if (allBox.checked) selectedCoachIds.add(b.value);
            });
            updateCoachFilterLabel();
            if (calendar) calendar.refetchEvents();
        });
    }

    if (options) {
        options.addEventListener('change', function(e) {
            if (!e.target.classList.contains('coach-filter-item')) return;
            selectedCoachIds = new Set(
                Array.from(document.querySelectorAll('.coach-filter-item'))
                    .filter(b => b.checked)
                    .map(b => b.value)
            );
            updateCoachFilterLabel();
            if (calendar) calendar.refetchEvents();
        });
    }
}

// ============================================================
// 視圖切換 (日 / 週)
// ============================================================
function initViewToggle() {
    const dayBtn = document.getElementById('viewDayBtn');
    const weekBtn = document.getElementById('viewWeekBtn');

    if (dayBtn) {
        dayBtn.addEventListener('click', function() {
            calendar.changeView(dayViewName());
            dayBtn.className = "px-3 py-1 rounded-md bg-white shadow-sm text-blue-600 font-bold transition-all";
            weekBtn.className = "px-3 py-1 rounded-md text-slate-600 font-medium hover:text-slate-900 transition-all";
        });
    }
    if (weekBtn) {
        weekBtn.addEventListener('click', function() {
            calendar.changeView(weekViewName());
            weekBtn.className = "px-3 py-1 rounded-md bg-white shadow-sm text-blue-600 font-bold transition-all";
            dayBtn.className = "px-3 py-1 rounded-md text-slate-600 font-medium hover:text-slate-900 transition-all";
        });
    }
}

// ============================================================
// 週次下拉選單
// ============================================================
function initWeekSelector() {
    const selector = document.getElementById('weekSelector');
    if (!selector) return;

    populateWeekOptions(selector);

    selector.addEventListener('change', function() {
        const selectedDate = new Date(this.value);
        calendar.gotoDate(selectedDate);
    });
}

function populateWeekOptions(selector) {
    selector.innerHTML = '';
    const today = new Date();
    const currentMonday = getMonday(today);

    for (let i = -6; i <= 6; i++) {
        const weekStart = new Date(currentMonday);
        weekStart.setDate(weekStart.getDate() + (i * 7));
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);

        const option = document.createElement('option');
        option.value = toLocalDateStr(weekStart);
        option.textContent = `${formatDate(weekStart)} ~ ${formatDate(weekEnd)}`;

        if (i === 0) {
            option.selected = true;
            option.textContent += ' (本週)';
        }
        selector.appendChild(option);
    }
}

function updateWeekSelector(viewStart) {
    const selector = document.getElementById('weekSelector');
    if (!selector) return;

    const viewMonday = getMonday(viewStart);
    const dateStr = toLocalDateStr(viewMonday);

    for (const opt of selector.options) {
        if (opt.value === dateStr) {
            opt.selected = true;
            return;
        }
    }

    // 選單只預先建立今天前後各 6 週；跳超出這個範圍時原本會找不到對應選項，
    // 選單就停在上一次選到的週次（看起來還停在本週）。這裡補一個該週的選項
    // 並選起來，讓顯示的週次永遠跟畫面上的日期一致。
    const weekEnd = new Date(viewMonday);
    weekEnd.setDate(weekEnd.getDate() + 6);
    const opt = document.createElement('option');
    opt.value = dateStr;
    opt.textContent = `${formatDate(viewMonday)} ~ ${formatDate(weekEnd)}`;
    opt.selected = true;
    // 依日期插到正確位置，選單才不會亂序
    const before = Array.from(selector.options).find(o => o.value > dateStr);
    selector.insertBefore(opt, before || null);
}

// 用「當地時間」組出 YYYY-MM-DD。不能用 toISOString()：它會先轉成 UTC，台北
// (UTC+8) 的當地午夜換算後會退回前一天，週次下拉選單的 value 就永遠對不上，
// 導致跳日/跳週時選單一直停在「(本週)」，看起來每天都是今天。
function toLocalDateStr(d) {
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${m}-${day}`;
}

function getMonday(d) {
    const date = new Date(d);
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(date.setDate(diff));
}

function formatDate(d) {
    const m = d.getMonth() + 1;
    const day = d.getDate();
    return `${m}/${day}`;
}

// ============================================================
// 新增課程 Modal
// ============================================================
let currentSelectionInfo = null;

function openCourseModal(info) {
    currentSelectionInfo = info;
    const modal = document.getElementById('courseModal');
    
    const startDate = info.start;
    const tzOffset = startDate.getTimezoneOffset() * 60000;
    const localISOTime = (new Date(startDate - tzOffset)).toISOString().slice(0, -1);
    
    document.getElementById('courseDate').value = localISOTime.split('T')[0];
    document.getElementById('startTime').value = padZero(startDate.getHours()) + ':' + padZero(startDate.getMinutes());
    const courseDateWeekdayEl = document.getElementById('courseDateWeekday');
    if (courseDateWeekdayEl) courseDateWeekdayEl.textContent = weekdayLabel(document.getElementById('courseDate').value);
    
    const diffMs = info.end - info.start;
    let diffMins = diffMs / 60000;
    if (diffMins < 60) diffMins = 60;
    document.getElementById('courseDuration').value = diffMins.toString();

    // 從拖曳選取的場地帶入預設值；手動點「新增課程」按鈕開啟時沒有場地資訊，
    // 維持選單目前的值（預設第一個選項）即可，使用者自己選。
    if (info.resource) {
        document.getElementById('courseLocation').value = info.resource.id;
    }

    document.getElementById('isTrial').checked = false;
    document.getElementById('trialFields').classList.add('hidden');
    const isRecurringCheck = document.getElementById('isRecurring');
    if (isRecurringCheck) {
        isRecurringCheck.checked = false;
        isRecurringCheck.disabled = false;
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeCourseModal() {
    const modal = document.getElementById('courseModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    currentSelectionInfo = null;
    document.getElementById('courseForm').reset();
}

// ============================================================
// 編輯課程 Modal
// ============================================================
function openEditCourseModal(event) {
    const modal = document.getElementById('editCourseModal');
    if (!modal) return;
    
    document.getElementById('editCourseId').value = event.id;
    document.getElementById('editStudentName').value = event.title;
    
    if (event.extendedProps.coach_id) {
        document.getElementById('editCoachName').value = event.extendedProps.coach_id;
    }
    
    document.getElementById('editCourseStatus').value = event.extendedProps.status || 'scheduled';
    const editLocationSelect = document.getElementById('editLocation');
    if (editLocationSelect) editLocationSelect.value = event.extendedProps.location || 'court_out_1';

    // 調課用的日期/時間欄位
    const start = event.start;
    const end = event.end;
    if (start) {
        document.getElementById('editCourseDate').value = toLocalDateStr(start);
        document.getElementById('editStartTime').value = padZero(start.getHours()) + ':' + padZero(start.getMinutes());
        updateEditCourseWeekday();

        const durationSelect = document.getElementById('editCourseDuration');
        if (durationSelect) {
            let mins = end ? Math.round((end - start) / 60000) : 60;
            if (mins <= 0) mins = 60;
            // 現有課程的長度理論上都是 60/90/120，但萬一有例外也要能正確帶出來，
            // 不然存檔時會被硬改成清單裡的第一個選項（等於偷偷改短課程長度）
            if (!Array.from(durationSelect.options).some(o => o.value === String(mins))) {
                const opt = document.createElement('option');
                opt.value = String(mins);
                opt.textContent = `${mins} 分鐘`;
                durationSelect.appendChild(opt);
            }
            durationSelect.value = String(mins);
        }
    }

    // 固定課程的其中一堂：提醒調課只影響這一堂
    const moveHint = document.getElementById('editRecurringMoveHint');
    if (moveHint) moveHint.classList.toggle('hidden', !event.extendedProps.is_recurring);
    
    const isTrial = event.extendedProps.is_trial || false;
    document.getElementById('editIsTrial').checked = isTrial;
    document.getElementById('editTrialCount').value = event.extendedProps.trial_count || 1;
    document.getElementById('editTrialFee').value = event.extendedProps.trial_fee || '';
    document.getElementById('editTrialFields').classList.toggle('hidden', !isTrial);
    currentEditIsRecurring = event.extendedProps.is_recurring || false;
    const editIsRecurringCheck = document.getElementById('editIsRecurring');
    if (editIsRecurringCheck) {
        // 已經是固定課程的話勾選框直接顯示成已勾選，不要讓小編以為還沒設定
        editIsRecurringCheck.checked = currentEditIsRecurring;
        editIsRecurringCheck.disabled = isTrial;
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function updateEditCourseWeekday() {
    const input = document.getElementById('editCourseDate');
    const label = document.getElementById('editCourseDateWeekday');
    if (input && label) label.textContent = weekdayLabel(input.value);
}

// 目前開啟的編輯視窗對應的課程是不是固定課程帶入的（決定刪除時要不要問範圍）
var currentEditIsRecurring = false;

function openDeleteScopeModal() {
    const m = document.getElementById('deleteScopeModal');
    if (!m) return;
    m.classList.remove('hidden');
    m.classList.add('flex');
}

function closeDeleteScopeModal() {
    const m = document.getElementById('deleteScopeModal');
    if (!m) return;
    m.classList.add('hidden');
    m.classList.remove('flex');
}

function performDelete(scope) {
    const courseId = document.getElementById('editCourseId').value;
    authFetch(`/api/courses/${courseId}?scope=${scope}`, { method: 'DELETE' })
        .then(async res => {
            const body = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(body.error || '刪除課程失敗');
            return body;
        })
        .then(data => {
            closeDeleteScopeModal();
            closeEditCourseModal();
            calendar.refetchEvents();
            if (scope === 'series' && data.message) alert(data.message);
        })
        .catch(err => alert('刪除發生錯誤：' + err.message));
}

function closeEditCourseModal() {
    const modal = document.getElementById('editCourseModal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.getElementById('editCourseForm').reset();
}

// ============================================================
// Modal 表單提交、點名簽到與請假處理
// ============================================================
function initModalEvents() {
    document.getElementById('cancelCourseBtn').addEventListener('click', closeCourseModal);

    // 日期選好後即時更新旁邊的星期幾提示，手動輸入日期時比較不會排錯天
    const courseDateInput = document.getElementById('courseDate');
    const courseDateWeekdayEl = document.getElementById('courseDateWeekday');
    if (courseDateInput && courseDateWeekdayEl) {
        courseDateInput.addEventListener('change', function() {
            courseDateWeekdayEl.textContent = weekdayLabel(this.value);
        });
    }

    const editCourseDateInput = document.getElementById('editCourseDate');
    if (editCourseDateInput) {
        editCourseDateInput.addEventListener('change', updateEditCourseWeekday);
    }

    // 手動「新增課程」按鈕：清單檢視（手機版的 listDay/listWeek）沒有時間格可以
    // 拖曳選取，select 事件不會觸發，所以需要這個永遠可點的按鈕當作另一個入口，
    // 用目前行事曆顯示的日期組出一個假的 selection info 交給 openCourseModal。
    // (權限由 base.html 的 .admin-only 顯示/隱藏機制把關，這裡不用重複檢查
    // isAdmin——那個變數是 DOMContentLoaded 那層閉包的區域變數，這個函式拿不到。)
    const addCourseBtn = document.getElementById('addCourseBtn');
    if (addCourseBtn) {
        addCourseBtn.addEventListener('click', function() {
            const anchor = calendar.getDate();
            const start = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate(), 10, 0, 0);
            const end = new Date(start.getTime() + 60 * 60000);
            openCourseModal({ start, end, resource: null });
        });
    }


    // 新增課程表單提交
    document.getElementById('courseForm').addEventListener('submit', function(e) {
        e.preventDefault();
        if (!currentSelectionInfo) return;
        
        const dateStr = document.getElementById('courseDate').value;
        const timeStr = document.getElementById('startTime').value;
        const durationMins = parseInt(document.getElementById('courseDuration').value, 10);
        
        const student = document.getElementById('studentName').value;
        const level = document.getElementById('studentLevel').value;
        const coach = document.getElementById('coachName').value;
        const isTrial = document.getElementById('isTrial').checked;
        const trialCount = document.getElementById('trialCount').value;
        const trialFee = document.getElementById('trialFee').value;
        const isRecurring = document.getElementById('isRecurring') ? document.getElementById('isRecurring').checked : false;

        if (!student) {
            alert('請填寫學生姓名！');
            return;
        }

        const studentId = studentNameToId[student] || null;
        if (!isTrial && !studentId) {
            alert(`找不到學生「${student}」的資料。非體驗課請從輸入框的建議清單中選擇既有學生；若是新學生，請先到「使用者管理」頁面新增資料。`);
            return;
        }

        const startDateTime = new Date(`${dateStr}T${timeStr}:00`);
        const endDateTime = new Date(startDateTime.getTime() + durationMins * 60000);
        const locationId = document.getElementById('courseLocation').value || 'court_out_1';

        const payload = {
            coach_id: coach,
            student_id: studentId,
            start_time: startDateTime.toISOString(),
            end_time: endDateTime.toISOString(),
            capacity: 4,
            location: locationId,
            title: student,
            description: level,
            is_trial: isTrial,
            trial_count: isTrial && trialCount ? parseInt(trialCount, 10) : null,
            trial_fee: isTrial && trialFee ? parseInt(trialFee, 10) : null,
            is_recurring: isRecurring
        };

        authFetch('/api/courses', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(async res => {
            const body = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(body.error || '新增課程失敗');
            return body;
        })
        .then(data => {
            calendar.refetchEvents();
            calendar.unselect();
            closeCourseModal();
            if (isRecurring && data.message) alert(data.message);
        })
        .catch(err => alert('新增課程發生錯誤：' + err.message));
    });

    // 編輯課程表單提交
    const editForm = document.getElementById('editCourseForm');
    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const courseId = document.getElementById('editCourseId').value;
            const isTrial = document.getElementById('editIsTrial').checked;
            const isRecurring = document.getElementById('editIsRecurring') ? document.getElementById('editIsRecurring').checked : false;

            // 調課：日期＋開始時間＋長度組回 start/end（跟新增課程的算法一致）
            const editDateStr = document.getElementById('editCourseDate').value;
            const editTimeStr = document.getElementById('editStartTime').value;
            const editDuration = parseInt(document.getElementById('editCourseDuration').value, 10) || 60;
            const editStart = new Date(`${editDateStr}T${editTimeStr}:00`);
            const editEnd = new Date(editStart.getTime() + editDuration * 60000);
            if (isNaN(editStart.getTime())) {
                alert('請填寫正確的日期與開始時間。');
                return;
            }

            const payload = {
                title: document.getElementById('editStudentName').value,
                coach_id: document.getElementById('editCoachName').value,
                location: document.getElementById('editLocation').value,
                start_time: editStart.toISOString(),
                end_time: editEnd.toISOString(),
                status: document.getElementById('editCourseStatus').value,
                is_trial: isTrial,
                trial_count: isTrial ? parseInt(document.getElementById('editTrialCount').value, 10) : null,
                trial_fee: isTrial ? parseInt(document.getElementById('editTrialFee').value, 10) : null,
                is_recurring: isRecurring
            };

            authFetch(`/api/courses/${courseId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(async res => {
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || '更新課程失敗');
                return body;
            })
            .then(data => {
                calendar.refetchEvents();
                closeEditCourseModal();
                if (isRecurring && data.message) alert(data.message);
            })
            .catch(err => alert('更新發生錯誤：' + err.message));
        });
    }

    // 課後點名簽到按鈕 (Check-in)
    const checkinBtn = document.getElementById('checkinCourseBtn');
    if (checkinBtn) {
        checkinBtn.addEventListener('click', function() {
            if (!confirm('確定執行課後點名簽到？\n課程將標記為已完成。')) return;
            const courseId = document.getElementById('editCourseId').value;
            authFetch(`/api/courses/${courseId}/checkin`, { method: 'POST' })
            .then(res => {
                if (!res.ok) throw new Error('簽到失敗');
                return res.json();
            })
            .then(d => {
                alert(d.message);
                calendar.refetchEvents();
                closeEditCourseModal();
            })
            .catch(err => alert('簽到失敗：' + err.message));
        });
    }

    // 標記請假按鈕
    const markLeaveBtn = document.getElementById('markLeaveBtn');
    if (markLeaveBtn) {
        markLeaveBtn.addEventListener('click', function() {
            if (!confirm('確定將此課程學員標記為請假？\n狀態將變更為請假(灰色置頂)，並釋出時段。')) return;
            const courseId = document.getElementById('editCourseId').value;
            authFetch(`/api/courses/${courseId}/leave`, {
                method: 'POST'
            })
            .then(res => {
                if (!res.ok) throw new Error('標記請假失敗');
                calendar.refetchEvents();
                closeEditCourseModal();
            })
            .catch(err => alert('請假處理失敗：' + err.message));
        });
    }

    // 刪除課程動作
    const deleteBtn = document.getElementById('deleteCourseBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function() {
            // 固定課程要先問清楚是「只停這一次」還是「整個固定課程都不要了」，
            // 不然小編只想停一週卻把整學期的排課砍掉（或以為刪掉了、下次載入
            // 又被自動生回來）。一般單堂課維持原本的簡單確認。
            if (currentEditIsRecurring) {
                openDeleteScopeModal();
            } else if (confirm('確定要永久刪除此課程嗎？此動作無法復原。')) {
                performDelete('occurrence');
            }
        });
    }

    const delOnce = document.getElementById('deleteOnceBtn');
    if (delOnce) delOnce.addEventListener('click', () => performDelete('occurrence'));

    const delSeries = document.getElementById('deleteSeriesBtn');
    if (delSeries) {
        delSeries.addEventListener('click', function() {
            if (confirm('確定要刪除整個固定課程嗎？\n往後每週都不會再自動帶入這位學生，尚未上課的同系列課程也會一併移除。')) {
                performDelete('series');
            }
        });
    }
}

function padZero(num) {
    return num < 10 ? '0' + num : num;
}
