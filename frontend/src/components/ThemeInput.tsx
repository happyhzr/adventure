import { useState, type SubmitEvent } from "react";

type Props = {
  onSubmit: (theme: string) => void;
};

function ThemeInput({ onSubmit }: Props) {
  const [theme, setTheme] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!theme.trim()) {
      setError("Please enter a theme name");
      return;
    }
    onSubmit(theme);
  }

  return (
    <div className="theme-input-container">
      <h2>Generate Your Adventure</h2>
      <p>Enter a theme for your interactive story</p>
      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <input
            type="text"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            placeholder="Enter a theme"
            className={error ? "error" : ""}
          />
          {error ? <p className="error-text">{error}</p> : null}
        </div>
        <button type="submit" className="generate-btn">
          Generate Story
        </button>
      </form>
    </div>
  );
}

export default ThemeInput;
