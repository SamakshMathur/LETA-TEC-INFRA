import { BASE_URL } from '../config/api';

export const advisoryService = {
  /**
   * Generates a formal legal advisory.
   * @param {string} query - The main query or facts.
   * @param {string|null} contextText - Optional context from previous answer.
   * @param {boolean} isManual - Whether this is a manual case study.
   */
  generateAdvisory: async (query, contextText = null, isManual = false) => {
    try {
      const response = await fetch(`${BASE_URL}/api/advisory/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: query,
          context_text: contextText,
          manual_case: isManual
        }),
      });

      if (!response.ok) {
        throw new Error(`Advisory Generation Failed: ${response.statusText}`);
      }

      const data = await response.json();
      return data; // { advisory: "...", status: "success" }
    } catch (error) {
      console.error("Advisory Service Error:", error);
      throw error;
    }
  }
};
