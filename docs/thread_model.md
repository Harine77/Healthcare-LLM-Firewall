# Threat Model
## Project
Securing Healthcare Chatbots Using LLM Firewalls

## 1. Intended application
A research prototype for patient-facing healthcare
question answering. It is not intended to diagnose,
prescribe treatment, or replace medical professionals.

## 2. Security objective
Reduce clinically harmful responses caused by prompt
injection while preserving legitimate medical questions.

## 3. Assets to protect
- Integrity of the chatbot's intended task
- Safety of responses under the selected threat model
- Separation of trusted application instructions from
  untrusted user prompts and retrieved content
- Integrity of firewall decisions and enforcement

## 4. Attacker capabilities
The attacker may:
- Submit a crafted user prompt.
- Attempt to override the chatbot's intended instructions.
- Supply malicious instructions through retrieved context,
  if the context-processing pathway is enabled.

The attacker is not assumed to control the model weights,
system configuration, server, or application credentials.

## 5. In-scope attacks
Primary:
- Direct prompt injection in user input.

Secondary, subject to implementation feasibility:
- Indirect prompt injection in supplied or retrieved context.

## 6. Out-of-scope threats for the first version
- Training-data poisoning and model-weight backdoors
- Autonomous tool execution and real EHR access
- Real patient data or PHI exfiltration
- Multimodal prompt injection
- A claim to prevent every medical hallucination or
  establish clinical safety in real-world deployment

## 7. Required security behavior
- All chatbot requests must pass through the backend gateway.
- Input and output decisions must be enforced by application
  code rather than by safety instructions alone.
- A response requiring validation must not be released if
  the validator times out, fails, or returns an invalid verdict.
- The system must return a safe fallback when it cannot
  establish that the response passed the required checks.

## 8. Evaluation boundary
This is a controlled research prototype evaluated on
documented public or otherwise properly licensed test data.
No real patient data will be used.