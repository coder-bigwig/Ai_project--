import React from 'react';

function TeacherLabSidebar({
  title = '\u6a21\u5757',
  items = [],
  activeKey = '',
  onSelect,
  headerContent = null,
}) {
  return (
    <aside className="teacher-lab-sidebar">
      {headerContent}
      {title ? <div className="teacher-lab-sidebar-title">{title}</div> : null}
      {items.map((item) => {
        const Icon = item.Icon;
        const enabled = item.enabled !== false;
        const isActive = activeKey === item.key;
        const description = String(item.tip || '').trim() || '\u00a0';

        return (
          <button
            key={item.key}
            type="button"
            className={`teacher-lab-menu-item ${isActive ? 'active' : ''}`}
            disabled={!enabled}
            onClick={() => {
              if (!enabled || typeof onSelect !== 'function') return;
              onSelect(item.key);
            }}
          >
            <span className="teacher-lab-menu-icon">{Icon ? <Icon /> : null}</span>
            <span className="teacher-lab-menu-text">
              <strong>{item.label}</strong>
              <small>{description}</small>
            </span>
          </button>
        );
      })}
    </aside>
  );
}

export default TeacherLabSidebar;
