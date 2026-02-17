// Service for fetching call summaries from the backend summarizer service

const SUMMARIZER_BASE_URL = "/api/summarizer";

export interface CallSummary {
  call_id: string;
  rolling_summary: {
    crm_paragraph?: string;
    bullets?: string[];
    [key: string]: any;
  };
  history_summary: string;
  promotions: {
    recommendations?: Array<{
      promo_id: string;
      name: string;
      description: string;
    }>;
    no_relevant_flag?: boolean;
  };
  chunks_processed: number;
}

/**
 * Fetch the call summary from the summarizer service
 * @param callId - The unique call ID
 * @returns Promise containing the call summary
 */
export const getCallSummary = async (callId: string): Promise<CallSummary> => {
  try {
    const response = await fetch(`${SUMMARIZER_BASE_URL}/summary/${callId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch summary: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Error fetching call summary:", error);
    throw error;
  }
};

/**
 * Fetch promotions for a specific call
 * @param callId - The unique call ID
 * @returns Promise containing promotion recommendations
 */
export const getCallPromotions = async (
  callId: string
): Promise<{
  recommendations: Array<any>;
  no_relevant_flag: boolean;
}> => {
  try {
    const response = await fetch(`${SUMMARIZER_BASE_URL}/promotions/${callId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch promotions: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Error fetching promotions:", error);
    return { recommendations: [], no_relevant_flag: true };
  }
};

/**
 * Save the call summary to the database
 * @param callId - The unique call ID
 * @param customerId - The customer ID
 * @param summary - The summary text to save
 * @returns Promise with the save result
 */
export const saveCallSummary = async (
  callId: string,
  customerId: number,
  summary: string
): Promise<{ interaction_id: number; summary: string }> => {
  try {
    const response = await fetch(`${SUMMARIZER_BASE_URL}/save_summary`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        call_id: callId,
        customer_id: customerId,
        summary: summary,
      }),
    });
    if (!response.ok) {
      throw new Error(`Failed to save summary: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Error saving call summary:", error);
    throw error;
  }
};
