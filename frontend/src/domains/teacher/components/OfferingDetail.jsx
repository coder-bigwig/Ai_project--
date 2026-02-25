import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import cover01 from '../../../shared/assets/system-covers/cover-01.svg';
import cover02 from '../../../shared/assets/system-covers/cover-02.svg';
import cover03 from '../../../shared/assets/system-covers/cover-03.svg';
import '../styles/OfferingDetail.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';
const OFFERING_COVER_STORAGE_KEY = 'offeringSystemCoverMap';
const SYSTEM_COVERS = [
  { id: 'system-01', label: '系统封面 1', src: cover01 },
  { id: 'system-02', label: '系统封面 2', src: cover02 },
  { id: 'system-03', label: '系统封面 3', src: cover03 },
];

function loadCoverSelectionMap() {
  if (typeof window === 'undefined') return {};
  try {
    const parsed = JSON.parse(localStorage.getItem(OFFERING_COVER_STORAGE_KEY) || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    return {};
  }
}

function persistCoverSelectionMap(nextMap) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(OFFERING_COVER_STORAGE_KEY, JSON.stringify(nextMap || {}));
  } catch (error) {
    // ignore write failures
  }
}

function hashString(value) {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function sortByLatestTime(a, b) {
  const aTime = new Date(a?.updated_at || a?.created_at || 0).getTime();
  const bTime = new Date(b?.updated_at || b?.created_at || 0).getTime();
  return bTime - aTime;
}

function normalizeCourseInfo(payload, fallback = {}) {
  return {
    courseId: String(payload?.template_course_id || fallback.courseId || '').trim(),
    courseName: String(payload?.template_course_name || fallback.courseName || '').trim(),
    teacherName: String(payload?.created_by || fallback.teacherName || '').trim(),
    offeringId: String(payload?.offering_id || fallback.offeringId || '').trim(),
    offeringCode: String(payload?.offering_code || fallback.offeringCode || '').trim(),
  };
}

function OfferingDetail({
  username,
  courseId = '',
  courseName = '',
  courseTeacher = '',
  offeringId = '',
  embedded = false,
}) {
  const { offeringId: routeOfferingId = '' } = useParams();
  const normalizedCourseId = String(courseId || '').trim();
  const normalizedOfferingId = String(offeringId || routeOfferingId || '').trim();
  const [loading, setLoading] = useState(true);
  const [coverPickerOpen, setCoverPickerOpen] = useState(false);
  const [coverSelectionMap, setCoverSelectionMap] = useState(() => loadCoverSelectionMap());
  const [courseInfo, setCourseInfo] = useState(() => ({
    courseId: normalizedCourseId,
    courseName: String(courseName || '').trim(),
    teacherName: String(courseTeacher || username || '').trim(),
    offeringId: normalizedOfferingId,
    offeringCode: '',
  }));

  useEffect(() => {
    let cancelled = false;
    const loadCourseInfo = async () => {
      const fallback = {
        courseId: normalizedCourseId,
        courseName: String(courseName || '').trim(),
        teacherName: String(courseTeacher || username || '').trim(),
        offeringId: normalizedOfferingId,
      };

      if (!username) {
        if (!cancelled) {
          setCourseInfo(fallback);
          setLoading(false);
        }
        return;
      }

      setLoading(true);
      try {
        if (normalizedCourseId) {
          const response = await axios.get(`${API_BASE_URL}/api/teacher/offerings`, {
            params: { teacher_username: username },
          });
          const rows = Array.isArray(response.data) ? response.data : [];
          const target = rows
            .filter((item) => String(item?.template_course_id || '').trim() === normalizedCourseId)
            .sort(sortByLatestTime)[0];

          if (!cancelled) {
            setCourseInfo(normalizeCourseInfo(target || {}, fallback));
          }
          return;
        }

        if (normalizedOfferingId) {
          const response = await axios.get(`${API_BASE_URL}/api/teacher/offerings/${encodeURIComponent(normalizedOfferingId)}`, {
            params: { teacher_username: username },
          });
          if (!cancelled) {
            setCourseInfo(normalizeCourseInfo(response.data || {}, fallback));
          }
          return;
        }

        if (!cancelled) {
          setCourseInfo(fallback);
        }
      } catch (error) {
        if (!cancelled) {
          setCourseInfo(fallback);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadCourseInfo();
    return () => {
      cancelled = true;
    };
  }, [courseName, courseTeacher, normalizedCourseId, normalizedOfferingId, username]);

  const courseCoverKey = useMemo(() => {
    if (courseInfo.courseId) return `course:${courseInfo.courseId}`;
    if (courseInfo.offeringId) return `offering:${courseInfo.offeringId}`;
    return '';
  }, [courseInfo.courseId, courseInfo.offeringId]);

  const activeCover = useMemo(() => {
    const selectedId = courseCoverKey ? String(coverSelectionMap?.[courseCoverKey] || '').trim() : '';
    const selectedCover = SYSTEM_COVERS.find((item) => item.id === selectedId);
    if (selectedCover) return selectedCover;
    const seed = String(courseInfo.courseId || courseInfo.offeringCode || courseInfo.courseName || 'system-cover-seed');
    const index = hashString(seed) % SYSTEM_COVERS.length;
    return SYSTEM_COVERS[index];
  }, [courseCoverKey, coverSelectionMap, courseInfo.courseId, courseInfo.courseName, courseInfo.offeringCode]);

  const handleSelectSystemCover = (coverId) => {
    if (!courseCoverKey || !coverId) return;
    setCoverSelectionMap((prev) => {
      const next = { ...(prev || {}), [courseCoverKey]: coverId };
      persistCoverSelectionMap(next);
      return next;
    });
    setCoverPickerOpen(false);
  };

  const hasCoreInfo = Boolean(String(courseInfo.courseName || '').trim() || String(courseInfo.teacherName || '').trim());
  const content = (
    <section className="offering-lite-card">
      {loading ? (
        <div className="offering-lite-empty">正在加载课程信息...</div>
      ) : !hasCoreInfo ? (
        <div className="offering-lite-empty">暂无课程信息</div>
      ) : (
        <>
          <div className="offering-lite-hero">
            <div className="offering-lite-cover">
              <img src={activeCover.src} alt={activeCover.label} />
            </div>
            <div className="offering-lite-cover-panel">
              <div className="offering-lite-cover-actions">
                <button type="button" onClick={() => setCoverPickerOpen((prev) => !prev)}>修改课程封面</button>
                <span>{activeCover.label}</span>
              </div>
              {coverPickerOpen ? (
                <div className="offering-lite-cover-picker">
                  {SYSTEM_COVERS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={item.id === activeCover.id ? 'active' : ''}
                      onClick={() => handleSelectSystemCover(item.id)}
                    >
                      <img src={item.src} alt={item.label} />
                      <span>{item.label}</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="offering-lite-info">
            <div className="offering-lite-info-item">
              <h3>课程名称</h3>
              <p>{courseInfo.courseName || '-'}</p>
            </div>
            <div className="offering-lite-info-item">
              <h3>课程教师</h3>
              <p>{courseInfo.teacherName || username || '-'}</p>
            </div>
          </div>
        </>
      )}
    </section>
  );

  if (embedded) {
    return <div className="offering-lite-embedded">{content}</div>;
  }
  return <div className="offering-lite-page">{content}</div>;
}

export default OfferingDetail;
