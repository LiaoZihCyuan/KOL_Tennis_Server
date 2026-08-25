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
                        html: `<span class="px-2 py-0.5 rounded-md text-xs font-bold border" style="background-color: ${coachColor}15; color: ${coachColor}; border-color: ${coachColor};">${coach}${location ? ' · ' + location : ''}</span>`
                    };
                }
                return {
                    html: `
                        <div class="w-full h-full p-1 flex items-center justify-center">
                            <span class="px-2 py-0.5 rounded-md text-[11px] font-bold border" style="background-color: ${coachColor}15; color: ${coachColor}; border-color: ${coachColor};">
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
                            <span class="text-xs font-medium px-1.5 py-0.5 rounded" style="background-color:${coachColor}15; color:${coachColor};">${coach || '待排教練'}</span>
                            ${unassignedBadge}${leaveBadge}${leaveReqBadge}${completedBadge}${trialBadge}
                        </div>
                    `
                };
            }

            let levelDiv = level ? `<div class="text-[11px] font-normal opacity-90 leading-tight break-words">${level}</div>` : '';
            let coachDiv = `<div class="text-[11px] ${isUnassigned ? 'text-slate-200 italic' : 'font-medium opacity-95'} leading-tight break-words">${coach || '待排教練'}</div>`;

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
                    let mappedEvents = data.map(course => {
                        let title = course.title || (course.students && course.students.length > 0 
                            ? course.students.map(s => s.name).join(', ') 
                            : '未命名課程');
                        
                        let status = course.status || 'scheduled';
                        
                        let bgColor = '#64748b'; // 預設灰階 (尚未排課/待排教練)
                        let borderColor = '#475569';
                        let coachDisplayName = course.coach_name;

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
                            coachDisplayName = '待排教練';
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
            if (label) label.textContent = dateInfo.view.title;
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
        locale: "zh_tw",
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
        })
        .catch(err => console.error('Error fetching coaches:', err));
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
        option.value = weekStart.toISOString().split('T')[0];
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
    const dateStr = viewMonday.toISOString().split('T')[0];

    for (const opt of selector.options) {
        if (opt.value === dateStr) {
            opt.selected = true;
            break;
        }
    }
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

            const payload = {
                title: document.getElementById('editStudentName').value,
                coach_id: document.getElementById('editCoachName').value,
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
