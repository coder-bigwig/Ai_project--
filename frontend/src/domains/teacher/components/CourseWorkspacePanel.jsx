import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import TeacherReview from './TeacherReview';
import TeacherUserManagement from './TeacherUserManagement';
import TeacherTeamManagement from './TeacherTeamManagement';
import ResourceFileManagement from './ResourceFileManagement';
import ProgressPanel from './ProgressPanel';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';
const TEACHER_COURSE_RESUME_KEY = 'teacherCourseResumeId';

function formatDate(v) {
  if (!v) return '-';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '-';
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function formatDateTime(v) {
  if (!v) return '-';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '-';
  return `${formatDate(v)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function toNumericScore(value) {
  const score = Number(value);
  return Number.isFinite(score) ? score : null;
}

function formatScoreValue(value) {
  const score = toNumericScore(value);
  if (score === null) return '';
  return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

function csvEscape(value) {
  const text = String(value ?? '');
  if (/[",\r\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function progressStatusKey(status) {
  const v = String(status || '').toLowerCase();
  if (v.includes('\u8bc4\u5206') || v.includes('graded')) return 'graded';
  if (v.includes('\u63d0\u4ea4') || v.includes('submit')) return 'submitted';
  if (v.includes('\u8fdb\u884c') || v.includes('progress')) return 'in-progress';
  return 'not-started';
}

function getErrorMessage(error, fallback) {
  if (error?.response?.status === 413) return '\u9644\u4ef6\u8fc7\u5927\uff0c\u8bf7\u538b\u7f29\u540e\u91cd\u8bd5\uff08\u5f53\u524d\u9650\u5236 200MB\uff09';
  return error?.response?.data?.detail || fallback;
}

function normalizeStringArray(values) {
  if (!Array.isArray(values)) return [];
  const seen = new Set();
  const result = [];
  values.forEach((item) => {
    const normalized = String(item || '').trim();
    const key = normalized.toLowerCase();
    if (!normalized || seen.has(key)) return;
    seen.add(key);
    result.push(normalized);
  });
  return result;
}

function CourseWorkspacePanel({
  username,
  userRole,
  courses,
  loading,
  progress,
  loadingProgress,
  onLoadProgress,
  submissions,
  loadingSubmissions,
  onLoadSubmissions,
  onGradeSubmission,
  courseMap,
  onCreateCourse,
  onDeleteCourse,
  onCreateExperiment,
  onEditExperiment,
  onDeleteExperiment,
  onListRecycleExperiments,
  onRestoreExperiment,
  onPermanentDeleteExperiment,
  routeCourseId = '',
  forceDetail = false,
  onOpenCourse,
  onExitDetail,
}) {
  const normalizedRouteCourseId = String(routeCourseId || '').trim();
  const [resumeCourseId] = useState(() => {
    const cachedCourseId = String(sessionStorage.getItem(TEACHER_COURSE_RESUME_KEY) || '').trim();
    if (cachedCourseId) sessionStorage.removeItem(TEACHER_COURSE_RESUME_KEY);
    return cachedCourseId;
  });
  const initialCourseId = normalizedRouteCourseId || resumeCourseId;
  const [viewMode, setViewMode] = useState((forceDetail || initialCourseId) ? 'detail' : 'home');
  const [selectedCourseId, setSelectedCourseId] = useState(initialCourseId);
  const [homeKeyword, setHomeKeyword] = useState('');
  const [detailMenu, setDetailMenu] = useState('management');
  const [assignmentKeyword, setAssignmentKeyword] = useState('');
  const [loadingRecycle, setLoadingRecycle] = useState(false);
  const [recycleRows, setRecycleRows] = useState([]);
  const [activeManageTab, setActiveManageTab] = useState('class-management');
  const [allOfferings, setAllOfferings] = useState([]);
  const [selectedCourseStudentCount, setSelectedCourseStudentCount] = useState(0);
  const [selectedCourseClassNames, setSelectedCourseClassNames] = useState([]);
  const [summaryRefreshTick, setSummaryRefreshTick] = useState(0);
  const [statisticsTab, setStatisticsTab] = useState('overview');
  const [statisticsExperimentId, setStatisticsExperimentId] = useState('all');
  const [statisticsKeyword, setStatisticsKeyword] = useState('');
  const [statisticsStudents, setStatisticsStudents] = useState([]);
  const [loadingStatisticsStudents, setLoadingStatisticsStudents] = useState(false);
  const [statisticsOverview, setStatisticsOverview] = useState({
    jupyter_experiment_visit_count: 0,
    active_student_count: 0,
    active_class_count: 0,
  });
  const [loadingStatisticsOverview, setLoadingStatisticsOverview] = useState(false);

  const selectedCourse = useMemo(() => {
    const needle = String(selectedCourseId || '').trim();
    if (!needle) return null;
    return (courses || []).find((item) => String(item?.id || '').trim() === needle) || null;
  }, [courses, selectedCourseId]);

  useEffect(() => {
    if (!normalizedRouteCourseId) return;
    setSelectedCourseId(normalizedRouteCourseId);
    setViewMode('detail');
  }, [normalizedRouteCourseId]);

  useEffect(() => {
    if (!forceDetail) return;
    setViewMode('detail');
  }, [forceDetail]);

  const selectedCourseExperiments = useMemo(
    () => (Array.isArray(selectedCourse?.experiments) ? selectedCourse.experiments : []),
    [selectedCourse]
  );

  const selectedCourseExperimentIds = useMemo(
    () => selectedCourseExperiments.map((item) => String(item?.id || '').trim()).filter(Boolean),
    [selectedCourseExperiments]
  );

  const selectedCourseExperimentIdSet = useMemo(
    () => new Set(selectedCourseExperimentIds),
    [selectedCourseExperimentIds]
  );

  const filteredCourseProgress = useMemo(
    () => (Array.isArray(progress) ? progress : []).filter((item) => selectedCourseExperimentIdSet.has(String(item?.experiment_id || '').trim())),
    [progress, selectedCourseExperimentIdSet]
  );

  const filteredCourseSubmissions = useMemo(
    () => (Array.isArray(submissions) ? submissions : []).filter((item) => selectedCourseExperimentIdSet.has(String(item?.experiment_id || '').trim())),
    [submissions, selectedCourseExperimentIdSet]
  );

  const loadCourseSubmissions = useCallback(async () => {
    if (typeof onLoadSubmissions !== 'function') return;
    await onLoadSubmissions(selectedCourseExperimentIds);
  }, [onLoadSubmissions, selectedCourseExperimentIds]);

  const loadStatisticsStudents = useCallback(async () => {
    const courseId = String(selectedCourse?.id || '').trim();
    if (!courseId || !username) {
      setStatisticsStudents([]);
      return;
    }

    setLoadingStatisticsStudents(true);
    try {
      const pageSize = 100;
      let page = 1;
      let total = 0;
      const rows = [];
      const seen = new Set();

      do {
        const res = await axios.get(
          `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(courseId)}/students`,
          {
            params: {
              teacher_username: username,
              page,
              page_size: pageSize,
            },
          }
        );
        const payload = res?.data || {};
        const items = Array.isArray(payload?.items) ? payload.items : [];
        total = Number(payload?.total || 0);

        items.forEach((item) => {
          const studentId = String(item?.student_id || '').trim();
          if (!studentId) return;
          const key = studentId.toLowerCase();
          if (seen.has(key)) return;
          seen.add(key);
          rows.push({
            student_id: studentId,
            real_name: String(item?.real_name || '').trim(),
            class_name: String(item?.class_name || '').trim(),
          });
        });

        if (items.length === 0) break;
        page += 1;
      } while (rows.length < total);

      setStatisticsStudents(rows);
    } catch (error) {
      console.error('loadStatisticsStudents failed', error);
      setStatisticsStudents([]);
    } finally {
      setLoadingStatisticsStudents(false);
    }
  }, [selectedCourse?.id, username]);

  const loadStatisticsOverview = useCallback(async () => {
    const courseId = String(selectedCourse?.id || '').trim();
    if (!courseId || !username) {
      setStatisticsOverview({
        jupyter_experiment_visit_count: 0,
        active_student_count: 0,
        active_class_count: 0,
      });
      return;
    }

    setLoadingStatisticsOverview(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/teacher/statistics`, {
        params: {
          teacher_username: username,
          course_id: courseId,
          days: 30,
        },
      });
      const payload = res?.data || {};
      setStatisticsOverview({
        jupyter_experiment_visit_count: Number(payload?.jupyter_experiment_visit_count || 0),
        active_student_count: Number(payload?.active_student_count || 0),
        active_class_count: Number(payload?.active_class_count || 0),
      });
    } catch (error) {
      console.error('loadStatisticsOverview failed', error);
      setStatisticsOverview({
        jupyter_experiment_visit_count: 0,
        active_student_count: 0,
        active_class_count: 0,
      });
    } finally {
      setLoadingStatisticsOverview(false);
    }
  }, [selectedCourse?.id, username]);

  const handleGradeSubmission = useCallback(async (submissionId, score, comment) => {
    if (typeof onGradeSubmission !== 'function') return;
    await onGradeSubmission(submissionId, score, comment);
    await loadCourseSubmissions();
  }, [onGradeSubmission, loadCourseSubmissions]);

  useEffect(() => {
    if (!Array.isArray(courses) || courses.length === 0) {
      if (!forceDetail && !normalizedRouteCourseId && viewMode === 'detail') setViewMode('home');
      if (selectedCourseId) setSelectedCourseId('');
      return;
    }

    if (normalizedRouteCourseId) {
      if (selectedCourseId !== normalizedRouteCourseId) {
        setSelectedCourseId(normalizedRouteCourseId);
      }
      if (viewMode !== 'detail') setViewMode('detail');
      return;
    }

    if (viewMode === 'detail' && !selectedCourseId) {
      setSelectedCourseId(String(courses[0]?.id || ''));
      return;
    }

    const exists = courses.some((item) => String(item?.id || '').trim() === String(selectedCourseId || '').trim());
    if (viewMode === 'detail' && selectedCourseId && !exists) {
      setSelectedCourseId(String(courses[0]?.id || ''));
    }
  }, [courses, forceDetail, normalizedRouteCourseId, selectedCourseId, viewMode]);

  const filteredHomeCourses = useMemo(() => {
    const needle = String(homeKeyword || '').trim().toLowerCase();
    if (!needle) return courses || [];
    return (courses || []).filter((item) => {
      const name = String(item?.name || '').toLowerCase();
      const desc = String(item?.description || '').toLowerCase();
      return name.includes(needle) || desc.includes(needle);
    });
  }, [courses, homeKeyword]);

  const handleDeleteCourseFromHome = useCallback(async () => {
    if (typeof onDeleteCourse !== 'function') return;
    if (!Array.isArray(filteredHomeCourses) || filteredHomeCourses.length === 0) {
      alert('\u6682\u65e0\u53ef\u5220\u9664\u7684\u8bfe\u7a0b');
      return;
    }
    if (filteredHomeCourses.length > 1) {
      const keyword = String(homeKeyword || '').trim();
      if (!keyword) {
        alert('\u8bf7\u5148\u5728\u641c\u7d22\u6846\u8f93\u5165\u8bfe\u7a0b\u540d\uff0c\u5b9a\u4f4d\u5230\u552f\u4e00\u8bfe\u7a0b\u540e\u518d\u5220\u9664');
      } else {
        alert(`\u5f53\u524d\u641c\u7d22\u5339\u914d\u5230 ${filteredHomeCourses.length} \u95e8\u8bfe\u7a0b\uff0c\u8bf7\u7ee7\u7eed\u8f93\u5165\u66f4\u7cbe\u786e\u7684\u5173\u952e\u8bcd\u540e\u518d\u5220\u9664`);
      }
      return;
    }

    try {
      const deleted = await onDeleteCourse(filteredHomeCourses[0]);
      if (deleted) setHomeKeyword('');
    } catch (error) {
      console.error('delete course failed', error);
      alert(getErrorMessage(error, '\u5220\u9664\u8bfe\u7a0b\u5931\u8d25'));
    }
  }, [filteredHomeCourses, homeKeyword, onDeleteCourse]);

  const refreshCourseSummary = useCallback(() => {
    setSummaryRefreshTick((prev) => prev + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadAllOfferings = async () => {
      if (!username) {
        setAllOfferings([]);
        return;
      }
      try {
        const res = await axios.get(`${API_BASE_URL}/api/teacher/offerings`, {
          params: { teacher_username: username },
        });
        if (cancelled) return;
        setAllOfferings(Array.isArray(res.data) ? res.data : []);
      } catch (error) {
        if (!cancelled) setAllOfferings([]);
      }
    };

    loadAllOfferings();
    return () => {
      cancelled = true;
    };
  }, [summaryRefreshTick, username]);

  useEffect(() => {
    setRecycleRows([]);
  }, [selectedCourseId]);

  useEffect(() => {
    setActiveManageTab('class-management');
  }, [selectedCourseId]);

  useEffect(() => {
    setStatisticsTab('overview');
    setStatisticsExperimentId('all');
    setStatisticsKeyword('');
    setStatisticsStudents([]);
    setStatisticsOverview({
      jupyter_experiment_visit_count: 0,
      active_student_count: 0,
      active_class_count: 0,
    });
  }, [selectedCourseId]);

  useEffect(() => {
    if (detailMenu !== 'management') return;
    if (activeManageTab === 'student-progress' && typeof onLoadProgress === 'function') {
      onLoadProgress();
      return;
    }
    if (activeManageTab === 'submission-review') {
      loadCourseSubmissions();
    }
  }, [activeManageTab, detailMenu, loadCourseSubmissions, onLoadProgress]);

  useEffect(() => {
    if (detailMenu !== 'statistics') return;
    loadCourseSubmissions();
    loadStatisticsStudents();
    loadStatisticsOverview();
  }, [detailMenu, loadCourseSubmissions, loadStatisticsStudents, loadStatisticsOverview]);

  const loadRecycleRows = useCallback(async () => {
    if (!selectedCourse?.id || typeof onListRecycleExperiments !== 'function') return;
    setLoadingRecycle(true);
    try {
      const rows = await onListRecycleExperiments(selectedCourse.id);
      setRecycleRows(Array.isArray(rows) ? rows : []);
    } catch (error) {
      console.error('load recycle failed', error);
      setRecycleRows([]);
      alert(getErrorMessage(error, '\u52a0\u8f7d\u56de\u6536\u7ad9\u5931\u8d25'));
    } finally {
      setLoadingRecycle(false);
    }
  }, [onListRecycleExperiments, selectedCourse?.id]);

  const openRecyclePage = useCallback(async () => {
    setDetailMenu('recycle');
    await loadRecycleRows();
  }, [loadRecycleRows]);

  useEffect(() => {
    if (detailMenu === 'recycle') {
      loadRecycleRows();
    }
  }, [detailMenu, loadRecycleRows]);

  const handleRestoreFromRecycle = useCallback(async (item) => {
    if (!item?.id || typeof onRestoreExperiment !== 'function') return;
    try {
      await onRestoreExperiment(item.id);
      await loadRecycleRows();
      alert('Assignment restored');
    } catch (error) {
      console.error('restore experiment failed', error);
      alert(getErrorMessage(error, '恢复作业失败'));
    }
  }, [onRestoreExperiment, loadRecycleRows]);

  const handlePermanentDeleteFromRecycle = useCallback(async (item) => {
    if (!item?.id || typeof onPermanentDeleteExperiment !== 'function') return;
    const targetTitle = String(item?.title || '\u8be5\u4f5c\u4e1a');
    if (!window.confirm(`\u786e\u5b9a\u5f7b\u5e95\u5220\u9664\u4f5c\u4e1a "${targetTitle}" \u5417\uff1f\u8be5\u64cd\u4f5c\u4e0d\u53ef\u6062\u590d\u3002`)) {
      return;
    }
    try {
      await onPermanentDeleteExperiment(item.id);
      await loadRecycleRows();
      alert('\u4f5c\u4e1a\u5df2\u5f7b\u5e95\u5220\u9664');
    } catch (error) {
      console.error('permanent delete experiment failed', error);
      alert(getErrorMessage(error, '\u5f7b\u5e95\u5220\u9664\u4f5c\u4e1a\u5931\u8d25'));
    }
  }, [onPermanentDeleteExperiment, loadRecycleRows]);

  const selectedCourseClassCount = useMemo(() => {
    const courseId = String(selectedCourse?.id || '').trim();
    if (!courseId) return 0;
    const classNames = new Set();

    (Array.isArray(allOfferings) ? allOfferings : []).forEach((item) => {
      const templateCourseId = String(item?.template_course_id || item?.course_id || '').trim();
      if (!templateCourseId || templateCourseId !== courseId) return;
      const status = String(item?.status || 'active').trim().toLowerCase();
      if (status === 'archived') return;
      const className = String(item?.class_name || '').trim();
      if (className) classNames.add(className);
    });

    (Array.isArray(selectedCourseClassNames) ? selectedCourseClassNames : []).forEach((name) => {
      const normalized = String(name || '').trim();
      if (normalized) classNames.add(normalized);
    });

    return classNames.size;
  }, [allOfferings, selectedCourse?.id, selectedCourseClassNames]);

  useEffect(() => {
    if (statisticsExperimentId === 'all') return;
    if (selectedCourseExperimentIdSet.has(statisticsExperimentId)) return;
    setStatisticsExperimentId('all');
  }, [selectedCourseExperimentIdSet, statisticsExperimentId]);

  useEffect(() => {
    let cancelled = false;
    const courseId = String(selectedCourse?.id || '').trim();

    if (!courseId || !username) {
      setSelectedCourseStudentCount(0);
      setSelectedCourseClassNames([]);
      return () => {
        cancelled = true;
      };
    }

    const loadCourseSummary = async () => {
      try {
        const [studentRes, classRes] = await Promise.allSettled([
          axios.get(
            `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(courseId)}/students`,
            {
              params: {
                teacher_username: username,
                page: 1,
                page_size: 1,
              },
            }
          ),
          axios.get(
            `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(courseId)}/students/classes`,
            {
              params: { teacher_username: username },
            }
          ),
        ]);
        if (cancelled) return;
        if (studentRes.status === 'fulfilled') {
          setSelectedCourseStudentCount(Number(studentRes.value?.data?.total || 0));
        } else {
          setSelectedCourseStudentCount(0);
        }

        if (classRes.status === 'fulfilled') {
          const classNames = normalizeStringArray(
            (Array.isArray(classRes.value?.data) ? classRes.value.data : [])
              .map((item) => String(item?.value || item?.label || item?.name || '').trim())
          );
          setSelectedCourseClassNames(classNames);
        } else {
          setSelectedCourseClassNames([]);
        }
      } catch (error) {
        if (!cancelled) {
          setSelectedCourseStudentCount(0);
          setSelectedCourseClassNames([]);
        }
      }
    };

    loadCourseSummary();
    return () => {
      cancelled = true;
    };
  }, [selectedCourse?.id, summaryRefreshTick, username]);

  const handleExitDetail = useCallback(() => {
    if (typeof onExitDetail === 'function') {
      onExitDetail();
      return;
    }
    setViewMode('home');
  }, [onExitDetail]);

  if (loading) return <div className="teacher-lab-loading">{"\u6b63\u5728\u52a0\u8f7d\u8bfe\u7a0b\u5e93..."}</div>;

  if (!forceDetail && !normalizedRouteCourseId) {
    return (
      <div className="teacher-course-home">
        <div className="teacher-course-home-toolbar">
          <div className="teacher-course-home-actions">
            <button type="button" className="teacher-lab-create-btn" onClick={onCreateCourse}>{'+ \u65b0\u5efa\u8bfe\u7a0b'}</button>
            <button
              type="button"
              className="teacher-lab-delete-btn"
              onClick={handleDeleteCourseFromHome}
              disabled={!Array.isArray(courses) || courses.length === 0}
            >
              {'- \u5220\u9664\u8bfe\u7a0b'}
            </button>
          </div>
          <div className="teacher-course-search-box">
            <input
              type="text"
              value={homeKeyword}
              onChange={(event) => setHomeKeyword(event.target.value)}
              placeholder={"\u641c\u7d22"}
            />
          </div>
        </div>

        {filteredHomeCourses.length === 0 ? (
          <div className="teacher-lab-empty">{"\u6682\u65e0\u8bfe\u7a0b\uff0c\u8bf7\u5148\u521b\u5efa\u8bfe\u7a0b\u3002"}</div>
        ) : (
          <div className="teacher-course-home-grid">
            {filteredHomeCourses.map((course) => {
              const summaryText = String(course?.description || '').trim() || `\u6388\u8bfe\u6559\u5e08\uff1a${course?.created_by || username || '-'}`;
              return (
                <button
                  key={course.id}
                  type="button"
                  className="teacher-course-home-card"
                  onClick={() => {
                    if (typeof onOpenCourse === 'function') {
                      onOpenCourse(course);
                      return;
                    }
                  }}
                >
                  <strong>{course?.name || '\u6211\u7684\u8bfe'}</strong>
                  <span>{summaryText}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  if (!selectedCourse) {
    return (
      <div className="teacher-lab-empty">
        {"\u672a\u627e\u5230\u8bfe\u7a0b\uff0c"}<button type="button" className="teacher-course-inline-btn" onClick={handleExitDetail}>{"\u8fd4\u56de\u9996\u9875"}</button>
      </div>
    );
  }

  const sideMenus = [
    { key: 'management', label: '\u7ba1\u7406', enabled: true },
    { key: 'resources', label: '\u8d44\u6599', enabled: true },
    { key: 'assignments', label: '\u4f5c\u4e1a', enabled: true },
    { key: 'recycle', label: '\u56de\u6536\u7ad9', enabled: true },
    { key: 'statistics', label: '\u7edf\u8ba1', enabled: true },
  ];

  const renderResources = () => (
    <div className="teacher-course-pane">
      <ResourceFileManagement
        username={username}
        courseId={selectedCourse?.id || ''}
        countLabel={"\u8bfe\u7a0b\u8d44\u6599\u5171"}
      />
    </div>
  );

  const renderAssignments = () => (
    <div className="teacher-course-pane teacher-course-assignment-pane">
      <div className="teacher-course-pane-toolbar">
        <div className="teacher-course-home-actions">
          <button
            type="button"
            className="teacher-lab-create-btn"
            onClick={() => onCreateExperiment(selectedCourse)}
          >
            {'+ \u65b0\u5efa\u4f5c\u4e1a'}
          </button>
        </div>
        <div className="teacher-course-search-box">
          <input
            type="text"
            placeholder={"\u641c\u7d22"}
            value={assignmentKeyword}
            onChange={(event) => setAssignmentKeyword(event.target.value)}
          />
        </div>
      </div>
      {(() => {
        const rows = (Array.isArray(selectedCourse?.experiments) ? selectedCourse.experiments : [])
          .filter((item) => {
            const needle = String(assignmentKeyword || '').trim().toLowerCase();
            if (!needle) return true;
            const title = String(item?.title || '').toLowerCase();
            const desc = String(item?.description || '').toLowerCase();
            const tags = Array.isArray(item?.tags) ? item.tags.join(' ').toLowerCase() : '';
            return title.includes(needle) || desc.includes(needle) || tags.includes(needle);
          });

        if (rows.length === 0) {
          return <div className="teacher-course-empty-board">{"\u6682\u65e0\u4f5c\u4e1a"}</div>;
        }

        return (
          <div className="teacher-course-assignment-list">
            <div className="teacher-course-assignment-head">
              <span className="title">{"\u4f5c\u4e1a\u540d\u79f0"}</span>
              <span>{"\u72b6\u6001"}</span>
              <span>{"\u96be\u5ea6"}</span>
              <span>{"\u521b\u5efa\u65f6\u95f4"}</span>
              <span>{"\u64cd\u4f5c"}</span>
            </div>
            {rows.map((item) => (
              <div key={item?.id || item?.title} className="teacher-course-assignment-row">
                <div className="title">
                  <strong>{item?.title || '\u672a\u547d\u540d\u4f5c\u4e1a'}</strong>
                  <small>{item?.description || '\u6682\u65e0\u63cf\u8ff0'}</small>
                </div>
                <span>{item?.published ? '\u5df2\u53d1\u5e03' : '\u8349\u7a3f'}</span>
                <span>{item?.difficulty || '-'}</span>
                <span>{formatDateTime(item?.created_at)}</span>
                <span className="teacher-course-assignment-actions">
                  <button
                    type="button"
                    className="teacher-course-inline-btn"
                    onClick={() => onEditExperiment(selectedCourse, item)}
                  >
                    {'\u7f16\u8f91'}
                  </button>
                  <button
                    type="button"
                    className="teacher-course-inline-btn danger"
                    onClick={async () => {
                      try {
                        await onDeleteExperiment(selectedCourse, item);
                      } catch (error) {
                        console.error('delete experiment failed', error);
                        alert(getErrorMessage(error, '\u5220\u9664\u4f5c\u4e1a\u5931\u8d25'));
                      }
                    }}
                  >
                    {'\u5220\u9664'}
                  </button>
                </span>
              </div>
            ))}
          </div>
        );
      })()}
      <div className="teacher-course-recycle">
        <button type="button" className="teacher-course-recycle-link" onClick={openRecyclePage}>{"\u56de\u6536\u7ad9"}</button>
      </div>
    </div>
  );

  const renderRecycle = () => (
    <div className="teacher-course-pane teacher-course-assignment-pane">
      <div className="teacher-course-pane-toolbar">
        <div className="teacher-course-home-actions">
          <button type="button" className="teacher-course-outline-btn" onClick={() => setDetailMenu('assignments')}>
            {"\u8fd4\u56de\u4f5c\u4e1a"}
          </button>
        </div>
        <button
          type="button"
          className="teacher-course-plain-btn"
          onClick={() => loadRecycleRows()}
          disabled={loadingRecycle}
        >
          {"\u5237\u65b0"}
        </button>
      </div>

      <div className="teacher-course-recycle-panel">
        <div className="teacher-course-recycle-head">
          <strong>{"\u56de\u6536\u7ad9"}</strong>
          <span className="teacher-course-recycle-tip">{"\u5220\u9664\u540e\u7684\u4f5c\u4e1a\u572830\u5929\u5185\u53ef\u6062\u590d"}</span>
        </div>

        {loadingRecycle ? (
          <div className="teacher-course-recycle-empty">{"\u6b63\u5728\u52a0\u8f7d\u56de\u6536\u7ad9..."}</div>
        ) : recycleRows.length === 0 ? (
          <div className="teacher-course-recycle-empty">{"\u56de\u6536\u7ad9\u4e3a\u7a7a"}</div>
        ) : (
          <div className="teacher-course-assignment-list teacher-course-recycle-list">
            <div className="teacher-course-assignment-head">
              <span className="title">{"\u4f5c\u4e1a\u540d\u79f0"}</span>
              <span>{"\u5220\u9664\u65f6\u95f4"}</span>
              <span>{"\u8fc7\u671f\u65f6\u95f4"}</span>
              <span>{"\u72b6\u6001"}</span>
              <span>{"\u64cd\u4f5c"}</span>
            </div>
            {recycleRows.map((item) => (
              <div key={item?.id || item?.title} className="teacher-course-assignment-row">
                <div className="title">
                  <strong>{item?.title || '\u672a\u547d\u540d\u4f5c\u4e1a'}</strong>
                  <small>{item?.description || '\u6682\u65e0\u63cf\u8ff0'}</small>
                </div>
                <span>{formatDateTime(item?.deleted_at)}</span>
                <span>{formatDateTime(item?.expires_at)}</span>
                <span>{"\u53ef\u6062\u590d"}</span>
                <span className="teacher-course-assignment-actions">
                  <button
                    type="button"
                    className="teacher-course-inline-btn"
                    onClick={() => handleRestoreFromRecycle(item)}
                  >
                    {'\u6062\u590d'}
                  </button>
                  <button
                    type="button"
                    className="teacher-course-inline-btn danger"
                    onClick={() => handlePermanentDeleteFromRecycle(item)}
                  >
                    {'\u5f7b\u5e95\u5220\u9664'}
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
  const manageTabs = [
    { key: 'class-management', label: '\u73ed\u7ea7\u7ba1\u7406', enabled: true },
    { key: 'teacher-team', label: '\u6559\u5e08\u56e2\u961f\u7ba1\u7406', enabled: true },
    { key: 'student-progress', label: '\u5b66\u751f\u8fdb\u5ea6', enabled: true },
    { key: 'submission-review', label: '\u63d0\u4ea4\u5ba1\u9605', enabled: true },
  ];

  const renderClassManagement = () => (
    <div className="teacher-course-manage-content">
      <TeacherUserManagement
        username={username}
        userRole={userRole}
        courseId={selectedCourse?.id || ''}
        onRosterChanged={refreshCourseSummary}
      />
    </div>
  );

  const renderTeacherTeamManagement = () => (
    <div className="teacher-course-manage-content">
      <TeacherTeamManagement username={username} courseId={selectedCourse?.id || ''} />
    </div>
  );

  const renderProgressManagement = () => (
    <div className="teacher-course-manage-content">
      <div className="teacher-course-manage-toolbar">
        <button type="button" className="teacher-course-plain-btn" onClick={() => typeof onLoadProgress === 'function' && onLoadProgress()}>
          {'\u5237\u65b0\u6570\u636e'}
        </button>
      </div>
      <ProgressPanel progress={filteredCourseProgress} loading={loadingProgress} courseMap={courseMap} />
    </div>
  );

  const renderReviewManagement = () => (
    <div className="teacher-course-manage-content">
      <div className="teacher-course-manage-toolbar">
        <button type="button" className="teacher-course-plain-btn" onClick={loadCourseSubmissions}>
          {'\u5237\u65b0\u6570\u636e'}
        </button>
      </div>
      <div className="teacher-lab-section">
        <TeacherReview
          username={username}
          submissions={filteredCourseSubmissions}
          loading={loadingSubmissions}
          onGrade={handleGradeSubmission}
        />
      </div>
    </div>
  );

  const renderManagement = () => (
    <div className="teacher-course-pane teacher-course-manage-pane">
      <div className="teacher-course-manage-tabs">
        {manageTabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeManageTab === tab.key ? 'active' : ''}
            disabled={!tab.enabled}
            onClick={() => {
              if (!tab.enabled) return;
              setActiveManageTab(tab.key);
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeManageTab === 'class-management' ? renderClassManagement() : null}
      {activeManageTab === 'teacher-team' ? renderTeacherTeamManagement() : null}
      {activeManageTab === 'student-progress' ? renderProgressManagement() : null}
      {activeManageTab === 'submission-review' ? renderReviewManagement() : null}
      {activeManageTab !== 'class-management' && activeManageTab !== 'teacher-team' && activeManageTab !== 'student-progress' && activeManageTab !== 'submission-review' ? (
        <div className="teacher-course-empty-board">{'\u8be5\u529f\u80fd\u6b63\u5728\u5efa\u8bbe\u4e2d'}</div>
      ) : null}
    </div>
  );

  const renderStatistics = () => {
    const monthJupyterVisitCount = Number(statisticsOverview?.jupyter_experiment_visit_count || 0);
    const monthActiveClassCount = Number(statisticsOverview?.active_class_count || 0);

    const experimentOptions = [
      { id: 'all', title: '\u5168\u90e8\u4f5c\u4e1a' },
      ...selectedCourseExperiments.map((item) => ({
        id: String(item?.id || '').trim(),
        title: String(item?.title || '').trim() || '\u672a\u547d\u540d\u4f5c\u4e1a',
      })),
    ];

    const experimentMap = {};
    selectedCourseExperiments.forEach((item) => {
      const experimentId = String(item?.id || '').trim();
      if (!experimentId) return;
      experimentMap[experimentId] = {
        id: experimentId,
        title: String(item?.title || '').trim() || '\u672a\u547d\u540d\u4f5c\u4e1a',
      };
    });

    const keywordNeedle = String(statisticsKeyword || '').trim().toLowerCase();
    const visibleStudents = (Array.isArray(statisticsStudents) ? statisticsStudents : []).filter((student) => {
      if (!keywordNeedle) return true;
      const studentId = String(student?.student_id || '').toLowerCase();
      const realName = String(student?.real_name || '').toLowerCase();
      const className = String(student?.class_name || '').toLowerCase();
      return studentId.includes(keywordNeedle) || realName.includes(keywordNeedle) || className.includes(keywordNeedle);
    });

    const selectedExperiments = statisticsExperimentId === 'all'
      ? selectedCourseExperiments
      : selectedCourseExperiments.filter((item) => String(item?.id || '').trim() === statisticsExperimentId);
    const totalAssignmentCount = selectedExperiments.length;

    const submissionMap = new Map();
    (Array.isArray(filteredCourseSubmissions) ? filteredCourseSubmissions : []).forEach((item) => {
      const studentId = String(item?.student_id || '').trim();
      const experimentId = String(item?.experiment_id || '').trim();
      if (!studentId || !experimentId) return;
      const key = `${studentId}::${experimentId}`;
      const existing = submissionMap.get(key);
      if (!existing) {
        submissionMap.set(key, item);
        return;
      }
      const existingTs = new Date(existing?.submit_time || existing?.updated_at || existing?.created_at || 0).getTime();
      const candidateTs = new Date(item?.submit_time || item?.updated_at || item?.created_at || 0).getTime();
      if (candidateTs >= existingTs) submissionMap.set(key, item);
    });

    const buildSubmissionSnapshot = (submission) => {
      const statusKey = progressStatusKey(submission?.status);
      const scoreValue = toNumericScore(submission?.score);
      const hasSubmitted = Boolean(
        submission
          && (statusKey === 'submitted' || statusKey === 'graded' || submission?.submit_time)
      );
      const missing = !hasSubmitted || scoreValue === null;
      return {
        missing,
        scoreValue,
        scoreText: missing ? '\u7f3a\u4ea4' : formatScoreValue(scoreValue),
        statusText: missing ? '\u7f3a\u4ea4' : (statusKey === 'graded' ? '\u5df2\u8bc4\u5206' : '\u5df2\u63d0\u4ea4'),
        submitTimeText: missing ? '\u7f3a\u4ea4' : formatDateTime(submission?.submit_time),
      };
    };

    const aggregateRows = visibleStudents.map((student) => {
      const studentId = String(student?.student_id || '').trim();
      let scoreSum = 0;
      let submittedCount = 0;

      selectedExperiments.forEach((experiment) => {
        const experimentId = String(experiment?.id || '').trim();
        const submission = submissionMap.get(`${studentId}::${experimentId}`);
        const snapshot = buildSubmissionSnapshot(submission);
        if (snapshot.missing) return;
        submittedCount += 1;
        scoreSum += snapshot.scoreValue || 0;
      });

      const missingCount = Math.max(totalAssignmentCount - submittedCount, 0);
      const averageScore = submittedCount > 0 ? (scoreSum / submittedCount) : null;
      return {
        student_id: studentId || '-',
        real_name: String(student?.real_name || '').trim() || '-',
        class_name: String(student?.class_name || '').trim() || '-',
        submitted_count: submittedCount,
        missing_count: missingCount,
        average_score: averageScore,
      };
    });

    const singleAssignment = statisticsExperimentId === 'all' ? null : experimentMap[statisticsExperimentId];
    const singleRows = singleAssignment ? visibleStudents.map((student) => {
      const studentId = String(student?.student_id || '').trim();
      const submission = submissionMap.get(`${studentId}::${singleAssignment.id}`);
      const snapshot = buildSubmissionSnapshot(submission);
      return {
        student_id: studentId || '-',
        real_name: String(student?.real_name || '').trim() || '-',
        class_name: String(student?.class_name || '').trim() || '-',
        assignment_name: singleAssignment.title,
        ...snapshot,
      };
    }) : [];

    const summary = (() => {
      const scoreValues = statisticsExperimentId === 'all'
        ? aggregateRows.map((item) => toNumericScore(item.average_score)).filter((item) => item !== null)
        : singleRows.map((item) => toNumericScore(item.scoreValue)).filter((item) => item !== null);
      const expectedCount = statisticsExperimentId === 'all'
        ? visibleStudents.length * totalAssignmentCount
        : singleRows.length;
      const submittedCount = statisticsExperimentId === 'all'
        ? aggregateRows.reduce((acc, item) => acc + item.submitted_count, 0)
        : singleRows.filter((item) => !item.missing).length;
      const missingStudentCount = statisticsExperimentId === 'all'
        ? aggregateRows.filter((item) => item.missing_count > 0).length
        : singleRows.filter((item) => item.missing).length;
      const averageScore = scoreValues.length > 0
        ? (scoreValues.reduce((acc, item) => acc + item, 0) / scoreValues.length)
        : null;
      const maxScore = scoreValues.length > 0 ? Math.max(...scoreValues) : null;
      const minScore = scoreValues.length > 0 ? Math.min(...scoreValues) : null;
      const submissionRate = expectedCount > 0 ? ((submittedCount / expectedCount) * 100) : 0;
      return {
        averageScore,
        maxScore,
        minScore,
        submissionRate,
        missingStudentCount,
      };
    })();

    const exportRows = [];
    if (totalAssignmentCount > 0) {
      visibleStudents.forEach((student) => {
        const studentId = String(student?.student_id || '').trim();
        selectedExperiments.forEach((experiment) => {
          const experimentId = String(experiment?.id || '').trim();
          const assignmentName = String(experiment?.title || '').trim() || '\u672a\u547d\u540d\u4f5c\u4e1a';
          const submission = submissionMap.get(`${studentId}::${experimentId}`);
          const snapshot = buildSubmissionSnapshot(submission);
          exportRows.push({
            '\u5b66\u53f7': studentId || '-',
            '\u59d3\u540d': String(student?.real_name || '').trim() || '-',
            '\u73ed\u7ea7': String(student?.class_name || '').trim() || '-',
            '\u4f5c\u4e1a\u540d\u79f0': assignmentName,
            '\u6210\u7ee9': snapshot.scoreText,
            '\u63d0\u4ea4\u72b6\u6001': snapshot.statusText,
            '\u63d0\u4ea4\u65f6\u95f4': snapshot.submitTimeText,
          });
        });
      });
    }

    const handleExportScores = () => {
      if (exportRows.length === 0) {
        alert('\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6682\u65e0\u53ef\u5bfc\u51fa\u6210\u7ee9');
        return;
      }
      const headers = ['\u5b66\u53f7', '\u59d3\u540d', '\u73ed\u7ea7', '\u4f5c\u4e1a\u540d\u79f0', '\u6210\u7ee9', '\u63d0\u4ea4\u72b6\u6001', '\u63d0\u4ea4\u65f6\u95f4'];
      const lines = [
        headers.map((item) => csvEscape(item)).join(','),
        ...exportRows.map((row) => headers.map((field) => csvEscape(row[field])).join(',')),
      ];
      const csv = lines.join('\r\n');
      const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      const courseName = String(selectedCourse?.name || 'course').trim() || 'course';
      const selectedAssignmentName = statisticsExperimentId === 'all'
        ? 'all-assignments'
        : (experimentMap[statisticsExperimentId]?.title || 'assignment');
      const safeCourseName = courseName.replace(/[\\/:*?"<>|]/g, '_');
      const safeAssignmentName = String(selectedAssignmentName).replace(/[\\/:*?"<>|]/g, '_');
      link.href = url;
      link.download = `${safeCourseName}-${safeAssignmentName}-scores.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    };

    return (
      <div className="teacher-course-stat-layout">
        <div className="teacher-course-stat-top">
          <div className="teacher-course-stat-main">
            <h2>{selectedCourse?.name || '\u6211\u7684\u8bfe'}</h2>
            <p>{`\u8bfe\u7a0b\u6559\u5e08\uff1a${selectedCourse?.created_by || username || '-'}`}</p>
          </div>
          <div className="teacher-course-stat-metrics">
            <div><span>{'\u73ed\u7ea7\u6570'}</span><strong>{selectedCourseClassCount}</strong><em>{'\u4e2a'}</em></div>
            <div><span>{'\u9009\u8bfe\u5b66\u751f\u6570'}</span><strong>{selectedCourseStudentCount}</strong><em>{'\u4eba'}</em></div>
          </div>
        </div>

        <div className="teacher-course-stat-tabs">
          <button
            type="button"
            className={statisticsTab === 'overview' ? 'active' : ''}
            onClick={() => setStatisticsTab('overview')}
          >
            {'\u57fa\u7840\u6570\u636e'}
          </button>
          <button
            type="button"
            className={statisticsTab === 'scores' ? 'active' : ''}
            onClick={() => setStatisticsTab('scores')}
          >
            {'\u5b66\u751f\u6210\u7ee9'}
          </button>
        </div>

        <div className="teacher-course-stat-grid">
          {statisticsTab === 'overview' ? (
            <section className="teacher-course-stat-card">
              <h3>{'\u5b66\u60c5\u6982\u89c8'}</h3>
              <div className="teacher-course-stat-band">
                <div>
                  <span>{'\u8fd1\u4e00\u4e2a\u6708 JupyterHub \u5b9e\u9a8c\u8bbf\u95ee\u6b21\u6570'}</span>
                  <strong>{loadingStatisticsOverview ? '--' : monthJupyterVisitCount}</strong>
                  <em>{'\u6b21'}</em>
                </div>
                <div>
                  <span>{'\u8fd1\u4e00\u4e2a\u6708\u6d3b\u8dc3\u73ed\u7ea7\u6570'}</span>
                  <strong>{loadingStatisticsOverview ? '--' : monthActiveClassCount}</strong>
                  <em>{'\u4e2a'}</em>
                </div>
              </div>
              <div className="teacher-course-heatmap-placeholder"><strong>{'\u8fd17\u65e5\u5b66\u751f\u5728\u7ebf\u5b66\u4e60\u70ed\u529b\u56fe'}</strong></div>
            </section>
          ) : (
            <section className="teacher-course-stat-card">
              <h3>{'\u5b66\u751f\u6210\u7ee9'}</h3>
              <div className="teacher-course-score-toolbar">
                <div className="teacher-course-score-controls">
                  <label htmlFor="teacher-score-assignment-filter">{'\u4f5c\u4e1a'}</label>
                  <select
                    id="teacher-score-assignment-filter"
                    value={statisticsExperimentId}
                    onChange={(event) => setStatisticsExperimentId(event.target.value)}
                  >
                    {experimentOptions.map((item) => (
                      <option key={item.id} value={item.id}>{item.title}</option>
                    ))}
                  </select>
                </div>
                <div className="teacher-course-score-controls grow">
                  <label htmlFor="teacher-score-search">{'\u641c\u7d22'}</label>
                  <input
                    id="teacher-score-search"
                    type="text"
                    value={statisticsKeyword}
                    onChange={(event) => setStatisticsKeyword(event.target.value)}
                    placeholder={'\u8bf7\u8f93\u5165\u5b66\u53f7/\u59d3\u540d/\u73ed\u7ea7'}
                  />
                </div>
                <button
                  type="button"
                  className="teacher-lab-create-btn"
                  onClick={handleExportScores}
                  disabled={loadingSubmissions || loadingStatisticsStudents || exportRows.length === 0}
                >
                  {'\u5bfc\u51fa\u6210\u7ee9'}
                </button>
              </div>

              <div className="teacher-course-score-band">
                <div><span>{'\u5e73\u5747\u5206'}</span><strong>{summary.averageScore === null ? '--' : formatScoreValue(summary.averageScore)}</strong></div>
                <div><span>{'\u6700\u9ad8\u5206'}</span><strong>{summary.maxScore === null ? '--' : formatScoreValue(summary.maxScore)}</strong></div>
                <div><span>{'\u6700\u4f4e\u5206'}</span><strong>{summary.minScore === null ? '--' : formatScoreValue(summary.minScore)}</strong></div>
                <div><span>{'\u63d0\u4ea4\u7387'}</span><strong>{`${summary.submissionRate.toFixed(1)}%`}</strong></div>
                <div><span>{'\u7f3a\u4ea4\u4eba\u6570'}</span><strong>{summary.missingStudentCount}</strong></div>
              </div>

              {loadingSubmissions || loadingStatisticsStudents ? (
                <div className="teacher-course-score-empty">{'\u6b63\u5728\u52a0\u8f7d\u6210\u7ee9\u6570\u636e...'}</div>
              ) : totalAssignmentCount === 0 ? (
                <div className="teacher-course-score-empty">{'\u5f53\u524d\u8bfe\u7a0b\u6682\u65e0\u4f5c\u4e1a'}</div>
              ) : (
                <div className="teacher-lab-table-wrap">
                  <table className="teacher-lab-table teacher-course-score-table">
                    <thead>
                      {statisticsExperimentId === 'all' ? (
                        <tr>
                          <th>{'\u5b66\u53f7'}</th>
                          <th>{'\u59d3\u540d'}</th>
                          <th>{'\u73ed\u7ea7'}</th>
                          <th>{'\u5e73\u5747\u5206'}</th>
                          <th>{'\u5df2\u4ea4\u4f5c\u4e1a\u6570'}</th>
                          <th>{'\u7f3a\u4ea4\u4f5c\u4e1a\u6570'}</th>
                        </tr>
                      ) : (
                        <tr>
                          <th>{'\u5b66\u53f7'}</th>
                          <th>{'\u59d3\u540d'}</th>
                          <th>{'\u73ed\u7ea7'}</th>
                          <th>{'\u4f5c\u4e1a\u540d\u79f0'}</th>
                          <th>{'\u6210\u7ee9'}</th>
                          <th>{'\u63d0\u4ea4\u72b6\u6001'}</th>
                          <th>{'\u63d0\u4ea4\u65f6\u95f4'}</th>
                        </tr>
                      )}
                    </thead>
                    <tbody>
                      {statisticsExperimentId === 'all' ? (
                        aggregateRows.length === 0 ? (
                          <tr>
                            <td colSpan="6" className="teacher-lab-empty-row">{'\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6682\u65e0\u6570\u636e'}</td>
                          </tr>
                        ) : (
                          aggregateRows.map((row) => (
                            <tr key={`${row.student_id}-aggregate`}>
                              <td>{row.student_id}</td>
                              <td>{row.real_name}</td>
                              <td>{row.class_name}</td>
                              <td>
                                {row.average_score === null ? (
                                  <span className="teacher-course-missing-text">{'\u7f3a\u4ea4'}</span>
                                ) : formatScoreValue(row.average_score)}
                              </td>
                              <td>{row.submitted_count}</td>
                              <td>
                                {row.missing_count > 0 ? (
                                  <span className="teacher-course-missing-text">{row.missing_count}</span>
                                ) : row.missing_count}
                              </td>
                            </tr>
                          ))
                        )
                      ) : (
                        singleRows.length === 0 ? (
                          <tr>
                            <td colSpan="7" className="teacher-lab-empty-row">{'\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6682\u65e0\u6570\u636e'}</td>
                          </tr>
                        ) : (
                          singleRows.map((row) => (
                            <tr key={`${row.student_id}-${row.assignment_name}`}>
                              <td>{row.student_id}</td>
                              <td>{row.real_name}</td>
                              <td>{row.class_name}</td>
                              <td>{row.assignment_name}</td>
                              <td>
                                {row.missing ? (
                                  <span className="teacher-course-missing-text">{'\u7f3a\u4ea4'}</span>
                                ) : row.scoreText}
                              </td>
                              <td>
                                {row.missing ? (
                                  <span className="teacher-course-missing-text">{'\u7f3a\u4ea4'}</span>
                                ) : row.statusText}
                              </td>
                              <td>
                                {row.missing ? (
                                  <span className="teacher-course-missing-text">{'\u7f3a\u4ea4'}</span>
                                ) : row.submitTimeText}
                              </td>
                            </tr>
                          ))
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    );
  };

  const renderContent = () => {
    if (detailMenu === 'resources') return renderResources();
    if (detailMenu === 'assignments') return renderAssignments();
    if (detailMenu === 'recycle') return renderRecycle();
    if (detailMenu === 'management') return renderManagement();
    if (detailMenu === 'statistics') return renderStatistics();
    return renderResources();
  };

  return (
    <div className="teacher-course-detail-shell">
      <aside className="teacher-course-detail-sidebar">
        <button type="button" className="teacher-course-detail-cover" onClick={handleExitDetail}>
          <div className="teacher-course-detail-cover-links"><span>{'\u8fd4\u56de\u8bfe\u7a0b\u5e93'}</span></div>
        </button>
        <div className="teacher-course-detail-title">{selectedCourse?.name || '\u6211\u7684\u8bfe'}</div>

        <div className="teacher-course-detail-menu">
          {sideMenus.map((item) => (
            <button
              key={item.key}
              type="button"
              className={detailMenu === item.key ? 'active' : ''}
              disabled={!item.enabled}
              onClick={() => item.enabled && setDetailMenu(item.key)}
            >
              <span className="dot" />
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </aside>

      <main className="teacher-course-detail-main">
        {renderContent()}
      </main>
    </div>
  );
}

export default CourseWorkspacePanel;
