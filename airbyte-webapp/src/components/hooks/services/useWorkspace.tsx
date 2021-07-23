import { useFetcher, useResource } from "rest-hooks";

import WorkspaceResource, { Workspace } from "core/resources/Workspace";
import NotificationsResource from "core/resources/Notifications";
import { useAnalytics } from "../useAnalytics";

const useWorkspace = (): {
  workspace: Workspace;
  setInitialSetupConfig: (data: {
    email: string;
    anonymousDataCollection: boolean;
    news: boolean;
    securityUpdates: boolean;
  }) => Promise<void>;
  updatePreferences: (data: {
    email?: string;
    anonymousDataCollection: boolean;
    news: boolean;
    securityUpdates: boolean;
  }) => Promise<void>;
  updateWebhook: (data: { webhook: string }) => Promise<void>;
  finishOnboarding: (skipStep?: string) => Promise<void>;
  testWebhook: (webhook: string) => Promise<void>;
} => {
  const updateWorkspace = useFetcher(WorkspaceResource.updateShape());
  const tryWebhookUrl = useFetcher(NotificationsResource.tryShape());
  const { workspaces } = useResource(WorkspaceResource.listShape(), {});
  const workspace = useResource(WorkspaceResource.detailShape(), {
    workspaceId: workspaces[0].workspaceId,
  });

  const analyticsService = useAnalytics();

  const finishOnboarding = async (skipStep?: string) => {
    if (skipStep) {
      analyticsService.track("Skip Onboarding", {
        step: skipStep,
      });
    }

    await updateWorkspace(
      {},
      {
        workspaceId: workspace.workspaceId,
        initialSetupComplete: workspace.initialSetupComplete,
        anonymousDataCollection: workspace.anonymousDataCollection,
        news: workspace.news,
        securityUpdates: workspace.securityUpdates,
        displaySetupWizard: false,
      }
    );
  };

  const setInitialSetupConfig = async (data: {
    email: string;
    anonymousDataCollection: boolean;
    news: boolean;
    securityUpdates: boolean;
  }) => {
    await updateWorkspace(
      {},
      {
        workspaceId: workspace.workspaceId,
        initialSetupComplete: true,
        displaySetupWizard: true,
        ...data,
      }
    );
  };

  const updatePreferences = async (data: {
    email?: string;
    anonymousDataCollection: boolean;
    news: boolean;
    securityUpdates: boolean;
  }) => {
    await updateWorkspace(
      {},
      {
        workspaceId: workspace.workspaceId,
        initialSetupComplete: workspace.initialSetupComplete,
        displaySetupWizard: workspace.displaySetupWizard,
        notifications: workspace.notifications,
        ...data,
      }
    );
  };

  const testWebhook = async (webhook: string) => {
    await tryWebhookUrl(
      {
        notificationType: "slack",
        slackConfiguration: {
          webhook: webhook,
        },
      },
      {}
    );
  };

  const updateWebhook = async (data: { webhook: string }) => {
    await updateWorkspace(
      {},
      {
        workspaceId: workspace.workspaceId,
        initialSetupComplete: workspace.initialSetupComplete,
        displaySetupWizard: workspace.displaySetupWizard,
        anonymousDataCollection: workspace.anonymousDataCollection,
        news: workspace.news,
        securityUpdates: workspace.securityUpdates,
        notifications: [
          {
            notificationType: "slack",
            slackConfiguration: {
              webhook: data.webhook,
            },
          },
        ],
      }
    );
  };

  return {
    workspace,
    finishOnboarding,
    setInitialSetupConfig,
    updatePreferences,
    updateWebhook,
    testWebhook,
  };
};

export default useWorkspace;
