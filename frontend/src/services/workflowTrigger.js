import { start } from "workflow/api";
import { handleUserSignup } from "../workflows/userSignup";

/**
 * Service to trigger the user signup workflow.
 * This can be called from any UI component.
 * 
 * @param {string} email - The user's email address.
 * @returns {Promise<string>} - The ID of the workflow run.
 */
export async function triggerSignupWorkflow(email) {
  try {
    console.log(`Triggering signup workflow for ${email}...`);
    
    // The start() function initiates the durable workflow.
    // It returns quickly with a runId while the workflow continues in the background.
    const { runId } = await start(handleUserSignup, { 
      args: [email] 
    });
    
    console.log(`Workflow started successfully. Run ID: ${runId}`);
    return runId;
  } catch (error) {
    console.error("Failed to start workflow:", error);
    throw error;
  }
}
