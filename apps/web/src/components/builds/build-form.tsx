"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useSources, useCreateBuild, useUpdateBuild } from "@/lib/queries";
import type { Build } from "@mmaction2-action-dataset-builder/shared";

const schema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters").max(80),
  description: z.string().max(280).optional(),
  source_key: z.string().min(1, "Pick an ingested video"),
  strategy: z.enum(["fixed-stride", "scene-detect"]),
  window_seconds: z.coerce.number().positive().max(60),
  stride_seconds: z.coerce.number().positive().max(60),
  recognizer_model: z.enum(["tsn-r50-kinetics400", "tsm-r50-kinetics400"]),
  confidence_threshold: z.coerce.number().min(0).max(1),
  split_preset: z.enum(["70/15/15", "80/10/10", "60/20/20"]),
  version_tag: z.string().min(1).max(40),
  max_clips: z.coerce.number().int().positive().max(500),
});

type FormValues = z.infer<typeof schema>;

const CREATE_DEFAULTS: FormValues = {
  name: "",
  description: "",
  source_key: "",
  strategy: "fixed-stride",
  window_seconds: 5,
  stride_seconds: 5,
  recognizer_model: "tsn-r50-kinetics400",
  confidence_threshold: 0.3,
  split_preset: "70/15/15",
  version_tag: "v1",
  max_clips: 60,
};

function fromBuild(b: Build): FormValues {
  return {
    name: b.name,
    description: b.description,
    source_key: b.config.source_key,
    strategy: b.config.strategy,
    window_seconds: b.config.window_seconds,
    stride_seconds: b.config.stride_seconds,
    recognizer_model: b.config.recognizer_model as FormValues["recognizer_model"],
    confidence_threshold: b.config.confidence_threshold,
    split_preset: b.config.split_preset,
    version_tag: b.config.version_tag,
    max_clips: b.config.max_clips,
  };
}

export function BuildForm({ build }: { build?: Build }) {
  const router = useRouter();
  const isEdit = !!build;
  // Config is locked once a build has run (draft is the only editable state).
  const configLocked = isEdit && build.status !== "draft";
  const { data: sources = [] } = useSources();
  const create = useCreateBuild();
  const update = useUpdateBuild(build?.id ?? "");
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: isEdit ? fromBuild(build) : CREATE_DEFAULTS,
  });

  const strategy = form.watch("strategy");

  const onSubmit = async (values: FormValues) => {
    setSubmitting(true);
    const config = {
      source_key: values.source_key,
      strategy: values.strategy,
      window_seconds: values.window_seconds,
      stride_seconds: values.stride_seconds,
      recognizer_model: values.recognizer_model,
      confidence_threshold: values.confidence_threshold,
      split_preset: values.split_preset,
      version_tag: values.version_tag,
      max_clips: values.max_clips,
    };
    try {
      if (isEdit) {
        await update.mutateAsync({
          name: values.name,
          description: values.description ?? "",
          // Don't send config once it's locked (server would 409).
          ...(configLocked ? {} : { config }),
        });
        toast.success("Build updated");
        router.push(`/builds/${build.id}`);
      } else {
        const created = await create.mutateAsync({
          name: values.name,
          description: values.description ?? "",
          config,
        });
        toast.success("Build created — run it to label clips");
        router.push(`/builds/${created.id}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  };

  // Default hints only on the create form; the edit form opens pre-filled with
  // the build's real config, so we suppress the "default" guidance there.
  const hint = (text: string) => (isEdit ? undefined : text);

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Details</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Build name</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. Broadcast highlights v1" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="What this dataset is for (optional)"
                      className="resize-none"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Build configuration</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-6">
            {configLocked && (
              <p className="text-sm text-[var(--attention)]">
                Build config is locked because this build has already run. You
                can still rename it; create a new build to use different
                settings.
              </p>
            )}

            <FormField
              control={form.control}
              name="source_key"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Source video</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value}
                    disabled={configLocked}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full max-w-md">
                        <SelectValue placeholder="Pick an ingested video…" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {sources.length === 0 ? (
                        <SelectItem value="__none" disabled>
                          No videos — ingest one first
                        </SelectItem>
                      ) : (
                        sources.map((s) => (
                          <SelectItem key={s.key} value={s.key}>
                            {s.filename} ({s.size_human})
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    {hint("Pick an ingested video.") ??
                      "Videos you ingested land under the raw/ prefix on B2."}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="strategy"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Segmentation strategy</FormLabel>
                  <FormControl>
                    <RadioGroup
                      onValueChange={field.onChange}
                      value={field.value}
                      className="flex gap-6 pt-1"
                      disabled={configLocked}
                    >
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <RadioGroupItem value="fixed-stride" />
                        Fixed stride
                      </label>
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <RadioGroupItem value="scene-detect" />
                        Scene detect
                      </label>
                    </RadioGroup>
                  </FormControl>
                  <FormDescription>
                    {hint("Default fixed-stride: a sliding window. Scene-detect is content-aware (PySceneDetect).") ??
                      "Fixed-stride slides a window; scene-detect is content-aware."}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid gap-6 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="window_seconds"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Window length (s)</FormLabel>
                    <FormControl>
                      <Input type="number" step="0.5" min={0.5} disabled={configLocked} {...field} />
                    </FormControl>
                    <FormDescription>{hint("Default 5") ?? "Seconds per clip"}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {strategy === "fixed-stride" && (
                <FormField
                  control={form.control}
                  name="stride_seconds"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Stride (s)</FormLabel>
                      <FormControl>
                        <Input type="number" step="0.5" min={0.5} disabled={configLocked} {...field} />
                      </FormControl>
                      <FormDescription>{hint("Default 5") ?? "Gap between windows"}</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </div>

            <div className="grid gap-6 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="recognizer_model"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Recognizer model</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                      disabled={configLocked}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="tsn-r50-kinetics400">
                          TSN R50 · Kinetics-400 · fast/CPU-friendly
                        </SelectItem>
                        <SelectItem value="tsm-r50-kinetics400">
                          TSM R50 · Kinetics-400
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      {hint("Default TSN R50 — fast on CPU.") ??
                        "Real MMAction2 recognizer, Kinetics-400 labels."}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="split_preset"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Split preset</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                      disabled={configLocked}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="70/15/15">70 / 15 / 15</SelectItem>
                        <SelectItem value="80/10/10">80 / 10 / 10</SelectItem>
                        <SelectItem value="60/20/20">60 / 20 / 20</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      {hint("Default 70/15/15") ?? "train / val / test ratio"}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="grid gap-6 sm:grid-cols-3">
              <FormField
                control={form.control}
                name="confidence_threshold"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confidence threshold</FormLabel>
                    <FormControl>
                      <Input type="number" step="0.05" min={0} max={1} disabled={configLocked} {...field} />
                    </FormControl>
                    <FormDescription>{hint("Default 0.30") ?? "0–1; drops weak labels"}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="version_tag"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Version tag</FormLabel>
                    <FormControl>
                      <Input placeholder="v1" disabled={configLocked} {...field} />
                    </FormControl>
                    <FormDescription>{hint("Default v1") ?? "Release label"}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="max_clips"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Max clips</FormLabel>
                    <FormControl>
                      <Input type="number" step="1" min={1} disabled={configLocked} {...field} />
                    </FormControl>
                    <FormDescription>{hint("Default 60") ?? "CPU-demo cap"}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => router.back()}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Saving…" : isEdit ? "Save changes" : "Create build"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
