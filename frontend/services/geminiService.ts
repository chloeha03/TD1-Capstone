
import { GoogleGenAI, Chat, GenerateContentResponse } from "@google/genai";

// Singleton chat instance management for the session
let chatInstance: Chat | null = null;

/* Refactored to follow @google/genai guidelines: fresh initialization when needed and strict process.env usage */
export const getChatInstance = (): Chat => {
  if (!chatInstance) {
    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    chatInstance = ai.chats.create({
      model: 'gemini-3-pro-preview',
      config: {
        thinkingConfig: {
          thinkingBudget: 32768 // Maximum thinking budget for complex reasoning
        },
        systemInstruction: `You are an expert Call Center Assistant named "Nexus AI". 
        Your goal is to assist the human agent in solving complex customer problems.
        You have deep reasoning capabilities. Use them to analyze policies, technical issues, and billing discrepancies.
        Be concise but thorough in your reasoning. 
        Format your responses with Markdown for readability (lists, bold text, headers).
        If the user provides raw data or logs, analyze them step-by-step.`,
      },
    });
  }
  return chatInstance;
};

export const sendMessageToAssistant = async (message: string): Promise<AsyncIterable<GenerateContentResponse>> => {
  const chat = getChatInstance();
  
  try {
    const result = await chat.sendMessageStream({ message });
    return result;
  } catch (error) {
    console.error("Error sending message to Gemini:", error);
    throw error;
  }
};

/* Using gemini-3-pro-image-preview: fresh instance creation right before the call is required */
export const generateImageMockup = async (description: string): Promise<string | null> => {
  try {
    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    const prompt = `A photorealistic, high-fidelity UI screenshot of a banking call center agent software.
    Theme: Professional TD Bank Emerald Green.
    Content: ${description}.
    The interface should look modern, clean, with a dense information layout typical of enterprise software.
    Show specific UI elements like buttons, charts, and customer data tables.`;

    const response = await ai.models.generateContent({
      model: 'gemini-3-pro-image-preview',
      contents: { parts: [{ text: prompt }] },
      config: {
        imageConfig: {
          aspectRatio: "16:9",
          imageSize: "2K"
        }
      }
    });

    for (const part of response.candidates?.[0]?.content?.parts || []) {
      if (part.inlineData) {
        return `data:image/png;base64,${part.inlineData.data}`;
      }
    }
    return null;
  } catch (error) {
    console.error("Error generating image:", error);
    throw error;
  }
};

export const resetChat = () => {
  chatInstance = null;
};
