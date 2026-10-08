import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios, { type AxiosError } from "axios";
import LoadingStatus from "./LoadingStatus";

const API_BASE_URL = "/api";

function StoryLoader() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [story, setStory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStory(Number(id));
  }, [id]);

  async function loadStory(storyId: number) {
    try {
      const reponse = await axios.get(
        `${API_BASE_URL}/stories/${storyId}/complete`,
      );
      setStory(reponse.data);
    } catch (err) {
      const e = err as AxiosError;
      if (e.response?.status === 404) {
        setError("Story is not found");
      } else {
        setError("Failed to load story");
      }
    } finally {
      setLoading(false);
    }
  }

  function createNewStory() {
    navigate("/");
  }

  if (loading) {
    return <LoadingStatus theme={"story"} />;
  }

  if (error) {
    return (
      <div className="story-loader">
        <div className="error-message">
          <h2>Story Not Found</h2>
          <p>{error}</p>
          <button onClick={createNewStory}>Go to Story Generator</button>
        </div>
      </div>
    );
  }

  if (story) {
    return <div className="story-loader"></div>;
  }
}

export default StoryLoader;
