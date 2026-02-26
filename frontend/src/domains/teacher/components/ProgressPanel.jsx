import React, { useMemo, useState } from 'react';

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatDateTime(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return `${formatDate(value)} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function progressStatusKey(status) {
  const value = String(status || '').toLowerCase();
  if (value.includes('\u8bc4\u5206') || value.includes('graded')) return 'graded';
  if (value.includes('\u63d0\u4ea4') || value.includes('submit')) return 'submitted';
  if (value.includes('\u8fdb\u884c') || value.includes('progress')) return 'in-progress';
  return 'not-started';
}

function isCompleted(status) {
  const key = progressStatusKey(status);
  return key === 'submitted' || key === 'graded';
}

function ProgressPanel({ progress, loading, courseMap, onRefresh }) {
  const [filter, setFilter] = useState('all');
  const total = progress.length;
  const completed = useMemo(() => progress.filter((item) => isCompleted(item.status)).length, [progress]);
  const pending = total - completed;
  const rate = total > 0 ? ((completed / total) * 100).toFixed(1) : '0.0';

  const rows = useMemo(() => {
    if (filter === 'completed') return progress.filter((item) => isCompleted(item.status));
    if (filter === 'incomplete') return progress.filter((item) => !isCompleted(item.status));
    return progress;
  }, [filter, progress]);

  const statusLabel = {
    'not-started': '\u672a\u5f00\u59cb',
    'in-progress': '\u8fdb\u884c\u4e2d',
    submitted: '\u5df2\u63d0\u4ea4',
    graded: '\u5df2\u8bc4\u5206',
  };

  if (loading) return <div className="teacher-lab-loading">{'\u6b63\u5728\u52a0\u8f7d\u5b66\u751f\u8fdb\u5ea6...'}</div>;

  return (
    <div className="teacher-lab-section teacher-lab-progress">
      <div className="teacher-lab-progress-stats">
        <div className="teacher-lab-progress-stat"><span>{'\u603b\u4efb\u52a1'}</span><strong>{total}</strong></div>
        <div className="teacher-lab-progress-stat success"><span>{'\u5df2\u5b8c\u6210'}</span><strong>{completed}</strong></div>
        <div className="teacher-lab-progress-stat warning"><span>{'\u672a\u5b8c\u6210'}</span><strong>{pending}</strong></div>
        <div className="teacher-lab-progress-stat info"><span>{'\u5b8c\u6210\u7387'}</span><strong>{rate}%</strong></div>
      </div>

      <div className="teacher-lab-filter-row">
        <div className="teacher-lab-filter-left">
          <label htmlFor="teacher-progress-filter">{'\u72b6\u6001\u7b5b\u9009\uff1a'}</label>
          <select id="teacher-progress-filter" value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="all">{'\u5168\u90e8'}</option>
            <option value="completed">{'\u5df2\u5b8c\u6210'}</option>
            <option value="incomplete">{'\u672a\u5b8c\u6210'}</option>
          </select>
        </div>
        <button type="button" className="teacher-course-plain-btn" onClick={onRefresh}>
          {'\u5237\u65b0\u6570\u636e'}
        </button>
      </div>

      <div className="teacher-lab-table-wrap">
        <table className="teacher-lab-table">
          <thead>
            <tr>
              <th>{'\u7528\u6237\u6807\u8bc6'}</th>
              <th>{'\u5b9e\u9a8c\u6807\u9898'}</th>
              <th>{'\u72b6\u6001'}</th>
              <th>{'\u5f00\u59cb\u65f6\u95f4'}</th>
              <th>{'\u63d0\u4ea4\u65f6\u95f4'}</th>
              <th>{'\u8bc4\u5206'}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan="6" className="teacher-lab-empty-row">{'\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6682\u65e0\u6570\u636e'}</td>
              </tr>
            ) : (
              rows.map((item, index) => {
                const key = progressStatusKey(item.status);
                return (
                  <tr key={`${item.student_id}-${item.experiment_id}-${index}`}>
                    <td>{item.student_id || '-'}</td>
                    <td>{courseMap[item.experiment_id]?.title || item.experiment_id || '-'}</td>
                    <td><span className={`teacher-lab-progress-badge ${key}`}>{statusLabel[key] || item.status || '-'}</span></td>
                    <td>{formatDateTime(item.start_time)}</td>
                    <td>{formatDateTime(item.submit_time)}</td>
                    <td>{item.score === null || item.score === undefined ? '-' : item.score}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ProgressPanel;
