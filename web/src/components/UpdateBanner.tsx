// "A new version is ready" banner. App shows it only off the game screen, because a
// reload ends the game in progress (games are not restored after a reload).
export function UpdateBanner({ onReload = () => window.location.reload() }) {
  return (
    <div className="update-banner" role="status">
      <span>A new version is ready.</span>
      <button type="button" className="update-banner-btn" onClick={() => onReload()}>
        Update now
      </button>
    </div>
  );
}
