import { BASE_URL } from '../config/api';

export const advisoryService = {
  /**
   * Generates a formal legal advisory via streaming SSE.
   *
   * Uses /generate-stream internally so the connection stays alive regardless
   * of how long Claude takes — 2 min, 30 min, no cap.
   *
   * Returns the same shape as before: { advisory, pdf_url, status, cached }
   * so AdvisoryModal.jsx and any other caller need no changes.
   *
   * Optional: pass onToken(text) to receive progressive streaming updates
   * (e.g. to show a live preview while generating).
   *
   * @param {string} query
   * @param {string|null} contextText
   * @param {boolean} isManual
   * @param {function|null} onToken  — called with each streamed text chunk
   */
  generateAdvisory: async (query, contextText = null, isManual = false, onToken = null) => {
    const response = await fetch(`${BASE_URL}/api/advisory/generate-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // No timeout set on fetch itself — the ALB timeout is the real limit,
        // and streaming keeps the connection alive so there is no limit.
      },
      body: JSON.stringify({
        query,
        context_text: contextText,
        manual_case: isManual,
      }),
    });

    if (!response.ok) {
      throw new Error(`Advisory Generation Failed: ${response.statusText}`);
    }

    // Read the SSE stream, collect tokens, surface onToken callbacks
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';
    let pdfUrl = null;
    let cached = false;
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE lines are separated by \n\n
      const lines = buffer.split('\n\n');
      buffer = lines.pop(); // last element may be incomplete — keep in buffer

      for (const block of lines) {
        // Each block starts with "data: "
        const dataLine = block.split('\n').find(l => l.startsWith('data: '));
        if (!dataLine) continue;

        let event;
        try {
          event = JSON.parse(dataLine.slice(6)); // strip "data: "
        } catch {
          continue;
        }

        if (event.type === 'token') {
          fullText += event.text;
          if (typeof onToken === 'function') onToken(event.text);
        } else if (event.type === 'done') {
          pdfUrl = event.pdf_url ?? null;
          cached = event.cached ?? false;
        } else if (event.type === 'error') {
          throw new Error(event.detail || 'Advisory generation failed');
        }
      }
    }

    if (!fullText) {
      throw new Error('Received empty advisory from system.');
    }

    return {
      advisory: fullText,
      pdf_url: pdfUrl,
      status: 'success',
      cached,
    };
  },
};
