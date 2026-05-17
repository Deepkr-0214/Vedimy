import { AppState } from '../core/state.js';
import { api } from '../core/api.js';
import { showToast } from '../components/toast.js';

if (!AppState.getToken() || AppState.getUser()?.role !== 'host') {
  window.location.href = '/pages/login.html';
}

document.getElementById('logout-btn').addEventListener('click', () => {
  AppState.logout();
  window.location.href = '/pages/login.html';
});

let analyticsData = null;
let attendanceData = null;
let examScoresData = null;
let securityActivityData = null;

async function loadAnalytics() {
  try {
    analyticsData = await api.get('/analytics/dashboard');
    document.getElementById('stat-classes').textContent = analyticsData.total_classes;
    document.getElementById('stat-students').textContent = analyticsData.total_students;
    document.getElementById('stat-exams').textContent = analyticsData.total_exams_submitted;
    
    let totalViolations = 0;
    const labels = [];
    const data = [];
    
    for (const [type, count] of Object.entries(analyticsData.violations)) {
      totalViolations += count;
      labels.push(type.replace('_', ' ').toUpperCase());
      data.push(count);
    }
    
    document.getElementById('stat-violations').textContent = totalViolations;
    
    if (totalViolations > 0) {
      const ctx = document.getElementById('violationChart').getContext('2d');
      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: labels,
          datasets: [{
            data: data,
            backgroundColor: ['#EA4335', '#FBBC05', '#34A853', '#4285F4', '#8B5CF6'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: 'right', labels: { color: 'white' } }
          }
        }
      });
    }

    // Load Attendance Trend
    attendanceData = await api.get('/analytics/attendance-trend');
    if (attendanceData && attendanceData.length > 0) {
      const ctxAtt = document.getElementById('attendanceChart').getContext('2d');
      new Chart(ctxAtt, {
        type: 'line',
        data: {
          labels: attendanceData.map(d => d.date),
          datasets: [{
            label: 'Attendees',
            data: attendanceData.map(d => d.count),
            borderColor: '#4285F4',
            backgroundColor: 'rgba(66, 133, 244, 0.2)',
            fill: true,
            tension: 0.4
          }]
        },
        options: {
          responsive: true,
          scales: {
            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white', stepSize: 1 } },
            x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white' } }
          },
          plugins: { legend: { display: false } }
        }
      });
    }

    // Load Exam Scores
    examScoresData = await api.get('/analytics/exam-scores');
    if (examScoresData && examScoresData.length > 0) {
      const ctxScores = document.getElementById('examScoresChart').getContext('2d');
      new Chart(ctxScores, {
        type: 'bar',
        data: {
          labels: examScoresData.map(d => d.range),
          datasets: [{
            label: 'Students',
            data: examScoresData.map(d => d.count),
            backgroundColor: '#34A853',
            borderRadius: 4
          }]
        },
        options: {
          responsive: true,
          scales: {
            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white', stepSize: 1 } },
            x: { grid: { display: false }, ticks: { color: 'white' } }
          },
          plugins: { legend: { display: false } }
        }
      });
    }

    // Load full security activity for CSV
    securityActivityData = await api.get('/analytics/security-activity');

  } catch (e) {
    showToast('Failed to load analytics', 'error');
  }
}

document.getElementById('export-csv-btn').addEventListener('click', () => {
  if (!analyticsData) return showToast('No data to export', 'error');
  
  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += "Metric,Value\n";
  csvContent += `Total Classes,${analyticsData.total_classes}\n`;
  csvContent += `Total Students,${analyticsData.total_students}\n`;
  csvContent += `Total Exams Submitted,${analyticsData.total_exams_submitted}\n`;
  csvContent += `\nViolation Type,Count\n`;
  
  for (const [type, count] of Object.entries(analyticsData.violations)) {
    csvContent += `${type},${count}\n`;
  }

  if (securityActivityData && securityActivityData.security_logs) {
    csvContent += `\n--- Detailed Violation Logs ---\n`;
    csvContent += `Timestamp,Event Type,Details\n`;
    securityActivityData.security_logs.forEach(log => {
      csvContent += `${log.timestamp},${log.event_type},"${(log.details || '').replace(/"/g, '""')}"\n`;
    });
  }
  
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `Vedimy_Analytics_Report_${new Date().toISOString().split('T')[0]}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
});

document.getElementById('export-pdf-btn').addEventListener('click', () => {
  showToast('PDF Export started. Please wait...', 'info');
  // Simple print for PDF generation simulation
  window.print();
});

loadAnalytics();
