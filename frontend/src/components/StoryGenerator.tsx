import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import axios, { type AxiosError } from "axios";
import ThemeInput from "./ThemeInput";
import LoadingStatus from "./LoadingStatus";
import { API_BASE_URL } from "../util";

type StoryJob = {
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  story_id?: number | null;
  error?: string | null;
};

function StoryGenerator() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const creationController = useRef<AbortController | null>(null);

  useEffect(() => () => creationController.current?.abort(), []);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    const pollJobStatus = async function poll() {
      try {
        const response = await axios.get<StoryJob>(`${API_BASE_URL}/jobs/${jobId}`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        const { status, story_id, error: jobError } = response.data;
        if (jobError || status === "failed") {
          setError(jobError || "Failed to generate story");
          setLoading(false);
        } else if (status === "completed") {
          setLoading(false);
          if (story_id) navigate(`/story/${story_id}`);
          else setError("Story generation completed without a story ID");
        } else if (status === "pending" || status === "processing") {
          timer = setTimeout(poll, 5000);
        } else {
          setError("Received an unexpected story status");
          setLoading(false);
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        const e = err as AxiosError;
        setError(e.response?.status === 404
          ? "Story generation job was not found. Please try again."
          : `Failed to check story status: ${e.message}`);
        setLoading(false);
      }
    };

    void pollJobStatus();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [jobId, navigate]);

  async function generateStory(theme: string) {
    if (creationController.current || loading) return;
    const controller = new AbortController();
    creationController.current = controller;
    setLoading(true);
    setError(null);
    setTheme(theme);
    try {
      const response = await axios.post<StoryJob>(
        `${API_BASE_URL}/stories/create`, { theme }, { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      if (!response.data.job_id) throw new Error("No generation job ID was returned");
      setJobId(response.data.job_id);
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(`Failed to generate story: ${e instanceof Error ? e.message : String(e)}`);
      setLoading(false);
    } finally {
      if (creationController.current === controller) creationController.current = null;
    }
  }

  function reset() {
    setJobId(null);
    setError(null);
    setTheme("");
    setLoading(false);
  }

  return (
    <div className="story-generator">
      {error ? (
        <div className="error-message">
          <p>{error}</p>
          <button onClick={reset}>Try Again</button>
        </div>
      ) : null}
      {!jobId && !error && !loading ? <ThemeInput onSubmit={generateStory} /> : null}
      {loading ? <LoadingStatus theme={theme} /> : null}
    </div>
  );
}

export default StoryGenerator;
