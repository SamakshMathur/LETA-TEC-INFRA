import { sleep } from "workflow";
import { createUser, sendWelcomeEmail, sendOnboardingEmail } from "./steps";

export async function handleUserSignup(email: string) {
  "use workflow";

  // Step 1: Create the user
  const user = await createUser(email);
  
  // Step 2: Send welcome email immediately
  await sendWelcomeEmail(user);

  // Step 3: Wait for a specific duration
  // This state is persisted and the function execution suspends
  await sleep("5s");

  // Step 4: Send onboarding email
  await sendOnboardingEmail(user);

  return { 
    userId: user.id, 
    status: "onboarded",
    completedAt: new Date().toISOString()
  };
}
