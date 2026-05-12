var calendar;

document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('calendar');

    calendar = new FullCalendar.Calendar(calendarEl, {
        locale: 'zh-tw',
        initialView: 'resourceTimeGridWeek',
        // 關鍵：日期在第一層，場地在第二層，避免重複標籤
        datesAboveResources: true, 
        
        // 場地資源定義
        resources: [
            { id: 'court_out_1', title: '室外場 1' },
            { id: 'court_out_2', title: '室外場 2' },
            { id: 'court_in', title: '室內場' }
        ],

        // 設定時間軸範圍：早 10 到 晚 10
        slotMinTime: '10:00:00',
        slotMaxTime: '22:00:00',
        
        allDaySlot: false,
        headerToolbar: false, 
        stickyHeaderDates: true,
        expandRows: true, // 讓內容撐滿高度
        selectable: true, // 允許點擊及拖曳選取時間區塊
        selectMirror: true,

        // 渲染課程方塊內容：模仿 Excel 排版
        eventContent: function(arg) {
            let coach = arg.event.extendedProps.coach_name || '教練未定';
            let level = arg.event.extendedProps.level || '';
            let student = arg.event.title;

            return {
                html: `
                    <div class="w-full h-full cursor-pointer hover:opacity-90 transition-opacity p-1">
                        <div class="course-title font-bold">${student} <span class="font-normal text-[10px] opacity-80">${level}</span></div>
                        <div class="course-coach text-xs">教練：${coach}</div>
                    </div>
                `
            };
        },

        // 點擊新增課程
        select: function(info) {
            openCourseModal(info);
        },

        // 點擊既有課程進入編輯/取消模式
        eventClick: function(info) {
            openEditCourseModal(info.event);
        },

        // 取得資料庫真實數據
        events: function(fetchInfo, successCallback, failureCallback) {
            let startStr = fetchInfo.startStr;
            let endStr = fetchInfo.endStr;
            fetch(`/api/courses?start_date=${encodeURIComponent(startStr)}&end_date=${encodeURIComponent(endStr)}`)
                .then(response => response.json())
                .then(data => {
                    let mappedEvents = data.map(course => {
                        let title = course.students && course.students.length > 0 
                            ? course.students.map(s => s.name).join(', ') 
                            : ''; // 取消顯示「尚未報名」，統一以有名字才顯示
                        
                        let status = course.status || 'normal';
                        let bgColor = status === 'excused' ? '#f43f5e' : '#3b82f6';
                        
                        return {
                            id: course.course_id,
                            resourceId: course.location,
                            title: title,
                            start: course.start_time,
                            end: course.end_time,
                            backgroundColor: bgColor,
                            extendedProps: {
                                coach_name: course.coach_name,
                                coach_id: course.coach_id,
                                status: status,
                                level: course.description || ''
                            }
                        };
                    });
                    successCallback(mappedEvents);
                })
                .catch(err => {
                    console.error('Error fetching courses:', err);
                    failureCallback(err);
                });
        }
    });

    calendar.render();

    // 初始化左側迷你月曆並同步
    flatpickr("#mini-calendar", {
        inline: true,
        locale: "zh_tw",
        onChange: function(selectedDates) {
            if (selectedDates.length > 0) {
                calendar.gotoDate(selectedDates[0]);
            }
        }
    });
    
    // 初始化Modal的事件監聽
    initModalEvents();
    
    // 載入教練列表
    fetchCoaches();
});

function fetchCoaches() {
    fetch('/api/users/coaches')
        .then(response => response.json())
        .then(data => {
            const coachSelect = document.getElementById('coachName');
            const editCoachSelect = document.getElementById('editCoachName');
            
            data.forEach(coach => {
                const option = document.createElement('option');
                option.value = coach.id;
                option.textContent = coach.display_name;
                if (coachSelect) coachSelect.appendChild(option);
                
                // 同步填充編輯用的下拉選單
                if (editCoachSelect) {
                    const editOption = option.cloneNode(true);
                    editCoachSelect.appendChild(editOption);
                }
            });
        })
        .catch(err => console.error('Error fetching coaches:', err));
}

function getMockData() {
    let today = new Date().toISOString().split('T')[0];
    return [
        { 
            resourceId: 'court_out_1', 
            title: '廖子權', 
            start: today + 'T10:00:00', 
            end: today + 'T11:30:00', 
            backgroundColor: '#3b82f6', 
            extendedProps: { coach_name: '蔡', level: '中級' } 
        },
        { 
            resourceId: 'court_in', 
            title: '王大同', 
            start: today + 'T14:00:00', 
            end: today + 'T15:00:00', 
            backgroundColor: '#a855f7', 
            extendedProps: { coach_name: '張', level: '初級' } 
        },
        { 
            resourceId: 'court_out_2', 
            title: '李小明', 
            start: today + 'T19:00:00', 
            end: today + 'T20:30:00', 
            backgroundColor: '#f43f5e', 
            extendedProps: { coach_name: '湯', level: '高級', status: 'excused' } 
        }
    ];
}

let currentSelectionInfo = null;

function openCourseModal(info) {
    currentSelectionInfo = info;
    const modal = document.getElementById('courseModal');
    
    // 預設填入時間
    const startDate = info.start;
    document.getElementById('courseDate').value = startDate.toISOString().split('T')[0];
    
    // 格式化時間 (HH:mm)
    const startStr = padZero(startDate.getHours()) + ':' + padZero(startDate.getMinutes());
    document.getElementById('startTime').value = startStr;
    
    // 預設結束時間 (1小時或1.5小時，先預設跟著選取的長度，如果沒選長度就1小時)
    const diffMs = info.end - info.start;
    let diffMins = diffMs / 60000;
    if (diffMins < 60) diffMins = 60; // 至少1小時
    
    document.getElementById('courseDuration').value = diffMins.toString();
    
    // 顯示 Modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeCourseModal() {
    const modal = document.getElementById('courseModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    currentSelectionInfo = null;
    
    // 清空表單
    document.getElementById('courseForm').reset();
}

function openEditCourseModal(event) {
    const modal = document.getElementById('editCourseModal');
    if (!modal) {
        alert('找不到編輯視窗，請確認 calendar.html 已儲存，並嘗試清除瀏覽器快取 (Ctrl+F5)。');
        return;
    }
    
    const idInput = document.getElementById('editCourseId');
    if (idInput) idInput.value = event.id;
    
    const nameInput = document.getElementById('editStudentName');
    if (nameInput) nameInput.value = event.title;
    
    if (event.extendedProps.coach_id) {
        const coachInput = document.getElementById('editCoachName');
        if (coachInput) coachInput.value = event.extendedProps.coach_id;
    }
    
    const statusInput = document.getElementById('editCourseStatus');
    if (statusInput) statusInput.value = event.extendedProps.status || 'normal';
    
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeEditCourseModal() {
    const modal = document.getElementById('editCourseModal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    
    const form = document.getElementById('editCourseForm');
    if (form) form.reset();
}

function initModalEvents() {
    document.getElementById('cancelCourseBtn').addEventListener('click', closeCourseModal);
    
    document.getElementById('courseForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (!currentSelectionInfo) return;
        
        const dateStr = document.getElementById('courseDate').value;
        const timeStr = document.getElementById('startTime').value;
        const durationMins = parseInt(document.getElementById('courseDuration').value, 10);
        
        const student = document.getElementById('studentName').value;
        const level = document.getElementById('studentLevel').value;
        const coach = document.getElementById('coachName').value;
        
        if (!student || !coach) {
            alert('請填寫完整資訊');
            return;
        }
        
        // 計算開始與結束時間
        const startDateTime = new Date(`${dateStr}T${timeStr}:00`);
        const endDateTime = new Date(startDateTime.getTime() + durationMins * 60000);
        
        const locationId = currentSelectionInfo.resource ? currentSelectionInfo.resource.id : 'court_in';

        // 準備要送出的資料
        const payload = {
            coach_id: coach, // 選單的值已改為 UUID
            start_time: startDateTime.toISOString(),
            end_time: endDateTime.toISOString(),
            capacity: 4, // 預設值
            location: locationId,
            credit_cost: 1, // 預設值
            description: level
        };

        fetch('/api/courses', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('新增課程失敗');
            }
            return response.json();
        })
        .then(data => {
            alert('課程建立成功！');
            // 重新取得日曆資料以更新畫面
            calendar.refetchEvents();
            
            // 清除選取範圍並關閉 Modal
            calendar.unselect();
            closeCourseModal();
        })
        .catch(err => {
            console.error('Error creating course:', err);
            alert('新增課程發生錯誤：' + err.message);
        });
    });
    
    // 處理編輯課程表單送出
    const editForm = document.getElementById('editCourseForm');
    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const courseId = document.getElementById('editCourseId').value;
            const payload = {
                title: document.getElementById('editStudentName').value,
                coach_id: document.getElementById('editCoachName').value,
                status: document.getElementById('editCourseStatus').value
            };

            fetch(`/api/courses/${courseId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(response => {
                if (!response.ok) throw new Error('更新課程失敗');
                return response.json();
            })
            .then(data => {
                alert('課程狀態更新成功！');
                calendar.refetchEvents();
                closeEditCourseModal();
            })
            .catch(err => alert('更新發生錯誤：' + err.message));
        });
    }

    // 處理刪除（取消）課程動作
    const deleteBtn = document.getElementById('deleteCourseBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function() {
            if (!confirm('確定要取消此課程嗎？此動作無法復原。')) return;
            
            const courseId = document.getElementById('editCourseId').value;
            fetch(`/api/courses/${courseId}`, {
                method: 'DELETE'
            })
            .then(response => {
                if (!response.ok) throw new Error('取消課程失敗');
                alert('課程已成功取消！');
                calendar.refetchEvents();
                closeEditCourseModal();
            })
            .catch(err => alert('取消發生錯誤：' + err.message));
        });
    }
}

function padZero(num) {
    return num < 10 ? '0' + num : num;
}
