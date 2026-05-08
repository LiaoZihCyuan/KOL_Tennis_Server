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
                    <div class="course-title">${student} <span class="font-normal text-[10px] opacity-80">${level}</span></div>
                    <div class="course-coach">教練：${coach}</div>
                `
            };
        },

        // 點擊新增課程
        select: function(info) {
            openCourseModal(info);
        },

        // 測試模擬數據
        events: getMockData()
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
});

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
        
        // 決定顏色 (可以隨機或根據教練/程度)
        const colors = ['#3b82f6', '#a855f7', '#f43f5e', '#10b981', '#f59e0b'];
        const randomColor = colors[Math.floor(Math.random() * colors.length)];
        
        // 新增事件到日曆
        calendar.addEvent({
            resourceId: currentSelectionInfo.resource ? currentSelectionInfo.resource.id : 'court_in', // 若沒有選擇 resource，預設
            title: student,
            start: startDateTime,
            end: endDateTime,
            backgroundColor: randomColor,
            extendedProps: {
                coach_name: coach,
                level: level
            }
        });
        
        // 清除選取範圍並關閉 Modal
        calendar.unselect();
        closeCourseModal();
    });
}

function padZero(num) {
    return num < 10 ? '0' + num : num;
}
