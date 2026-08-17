var calendar;
var currentUser = null;

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
        initialView: 'resourceTimeGridWeek',
        datesAboveResources: true, 
        
        resources: [
            { id: 'court_out_1', title: '室外場 1' },
            { id: 'court_out_2', title: '室外場 2' },
            { id: 'court_in', title: '室內場' }
        ],

        slotMinTime: '10:00:00',
        slotMaxTime: '22:00:00',
        
        allDaySlot: false,
        headerToolbar: false, 
        stickyHeaderDates: true,
        expandRows: true,
        selectable: isAdmin, // 僅 Admin 可點選排課
        editable: isAdmin,   // 僅 Admin 支援直接拖曳調課 (Drag & Drop)
        selectMirror: true,

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
            .then(data => {
                calendar.refetchEvents();
                // 課程時長改變會連動重算點數（見 credit_cost 校正），這種情況務必讓小編看到，
                // 一般沒有點數變動的調課則不用跳窗打斷操作。
                if (data.message && data.message.includes('點數已由')) {
                    alert(data.message);
                }
            })
            .catch(err => {
                alert('調課失敗：' + err.message);
                info.revert();
            });
        },

        // 拖曳調整課程長度 (Resize) — editable:true 預設也會開放拖曳邊緣調整時長，
        // 若不接這個 callback，畫面上看起來調整成功，但其實沒送到後端，重新整理/切換
        // 週次後會整個復原，小編完全不會發現。這裡直接沿用跟 eventDrop 一樣的邏輯，
        // 讓時長變更能正確連動重算點數 (credit_cost)。
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
            .then(data => {
                calendar.refetchEvents();
                if (data.message) alert(data.message);
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

            if (isOtherStudent) {
                let coachColor = arg.event.extendedProps.coach_color || '#3b82f6';
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

            let isUnassigned = arg.event.extendedProps.is_unassigned;
            let leaveBadge = (status === 'cancelled') ? '<div class="text-[10px] bg-black/50 text-white px-1 rounded mt-0.5 inline-block font-normal">已請假</div>' : '';
            let leaveReqBadge = (arg.event.extendedProps.leave_status === 'requested') ? '<div class="text-[10px] bg-amber-500 text-white px-1 rounded mt-0.5 inline-block font-bold">請假待審</div>' : '';
            let unassignedBadge = isUnassigned ? '<div class="text-[10px] bg-slate-800 text-white px-1 rounded mt-0.5 inline-block font-bold">待排課</div>' : '';
            let trialBadge = isTrial ? `<div class="text-[10px] bg-amber-500 text-white font-bold px-1 rounded mt-0.5 inline-block">體驗${trialFee ? '$' + trialFee : ''}</div>` : '';
            let completedBadge = (status === 'completed') ? '<div class="text-[10px] bg-emerald-600 text-white px-1 rounded mt-0.5 inline-block font-normal">已簽到</div>' : '';
            let levelDiv = level ? `<div class="text-[11px] font-normal opacity-90 leading-tight break-words">${level}</div>` : '';
            let coachDiv = `<div class="text-[11px] ${isUnassigned ? 'text-slate-200 italic' : 'font-medium opacity-95'} leading-tight break-words">${coach || '待排教練'}</div>`;

            return {
                html: `
                    <div class="w-full h-full cursor-pointer hover:opacity-95 transition-opacity p-1 text-white flex flex-col justify-start text-left overflow-hidden">
                        <div class="font-bold text-[12px] leading-tight break-words">${student}</div>
                        ${levelDiv}
                        ${coachDiv}
                        ${unassignedBadge}
                        ${leaveBadge}
                        ${leaveReqBadge}
                        ${completedBadge}
                        ${trialBadge}
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
                                is_other_student: course.is_other_student || false
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
        }
    });

    calendar.render();

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
    if (isTrialCheck && trialFields) {
        isTrialCheck.addEventListener('change', function() {
            trialFields.classList.toggle('hidden', !this.checked);
        });
    }

    const editIsTrialCheck = document.getElementById('editIsTrial');
    const editTrialFields = document.getElementById('editTrialFields');
    if (editIsTrialCheck && editTrialFields) {
        editIsTrialCheck.addEventListener('change', function() {
            editTrialFields.classList.toggle('hidden', !this.checked);
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
            calendar.changeView('resourceTimeGridDay');
            dayBtn.className = "px-3 py-1 rounded-md bg-white shadow-sm text-blue-600 font-bold transition-all";
            weekBtn.className = "px-3 py-1 rounded-md text-slate-600 font-medium hover:text-slate-900 transition-all";
        });
    }
    if (weekBtn) {
        weekBtn.addEventListener('click', function() {
            calendar.changeView('resourceTimeGridWeek');
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
    
    document.getElementById('isTrial').checked = false;
    document.getElementById('trialFields').classList.add('hidden');

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

    modal.classList.remove('hidden');
    modal.classList.add('flex');
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
        
        if (!student || !coach) {
            alert('請填寫完整學生姓名與教練！');
            return;
        }

        const studentId = studentNameToId[student] || null;
        if (!isTrial && !studentId) {
            alert(`找不到學生「${student}」的資料。非體驗課請從輸入框的建議清單中選擇既有學生，才能正確連動扣點；若是新學生，請先到「使用者管理」頁面新增資料。`);
            return;
        }

        const startDateTime = new Date(`${dateStr}T${timeStr}:00`);
        const endDateTime = new Date(startDateTime.getTime() + durationMins * 60000);
        const locationId = currentSelectionInfo.resource ? currentSelectionInfo.resource.id : 'court_out_1';

        const payload = {
            coach_id: coach,
            student_id: studentId,
            start_time: startDateTime.toISOString(),
            end_time: endDateTime.toISOString(),
            capacity: 4,
            location: locationId,
            credit_cost: Math.max(1, Math.round(durationMins / 60)),
            title: student,
            description: level,
            is_trial: isTrial,
            trial_count: isTrial && trialCount ? parseInt(trialCount, 10) : null,
            trial_fee: isTrial && trialFee ? parseInt(trialFee, 10) : null
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
        .then(() => {
            calendar.refetchEvents();
            calendar.unselect();
            closeCourseModal();
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
            
            const payload = {
                title: document.getElementById('editStudentName').value,
                coach_id: document.getElementById('editCoachName').value,
                status: document.getElementById('editCourseStatus').value,
                is_trial: isTrial,
                trial_count: isTrial ? parseInt(document.getElementById('editTrialCount').value, 10) : null,
                trial_fee: isTrial ? parseInt(document.getElementById('editTrialFee').value, 10) : null
            };

            authFetch(`/api/courses/${courseId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => {
                if (!res.ok) throw new Error('更新課程失敗');
                return res.json();
            })
            .then(() => {
                calendar.refetchEvents();
                closeEditCourseModal();
            })
            .catch(err => alert('更新發生錯誤：' + err.message));
        });
    }

    // 課後點名簽到按鈕 (Check-in)
    const checkinBtn = document.getElementById('checkinCourseBtn');
    if (checkinBtn) {
        checkinBtn.addEventListener('click', function() {
            if (!confirm('確定執行課後點名簽到？\n課程將標記為已完成，並自動為學員扣抵 1 堂（依課程時數扣除對應點數）。')) return;
            const courseId = document.getElementById('editCourseId').value;
            authFetch(`/api/courses/${courseId}/checkin`, { method: 'POST' })
            .then(res => {
                if (!res.ok) throw new Error('簽到扣點失敗');
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
            if (!confirm('確定要永久刪除此課程嗎？此動作無法復原。')) return;
            const courseId = document.getElementById('editCourseId').value;
            authFetch(`/api/courses/${courseId}`, { method: 'DELETE' })
            .then(res => {
                if (!res.ok) throw new Error('刪除課程失敗');
                calendar.refetchEvents();
                closeEditCourseModal();
            })
            .catch(err => alert('刪除發生錯誤：' + err.message));
        });
    }
}

function padZero(num) {
    return num < 10 ? '0' + num : num;
}
