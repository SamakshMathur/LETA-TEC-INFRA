import { FatalError } from 'workflow';

export async function createUser(email: string) {
  "use step";
  
  // Simulate database creation delay
  console.log(`Creating user for ${email}...`);
  
  // In a real app, this would be a database call
  const user = {
    id: `usr_${Math.random().toString(36).slice(2, 11)}`,
    email,
    createdAt: new Date().toISOString()
  };
  
  return user;
}

export async function sendWelcomeEmail(user: { email: string; id: string }) {
  "use step";
  
  console.log(`Step: Sending welcome email to ${user.email}`);
  
  // Simulation of an external API call (e.g., Resend)
  // For now, we just return a success status
  return { 
    status: "sent", 
    provider: "SimulatedProvider",
    sentAt: new Date().toISOString()
  };
}

export async function sendOnboardingEmail(user: { email: string; id: string }) {
  "use step";
  
  console.log(`Step: Sending onboarding email to ${user.email}`);
  
  return { 
    status: "sent", 
    type: "onboarding",
    sentAt: new Date().toISOString()
  };
}
