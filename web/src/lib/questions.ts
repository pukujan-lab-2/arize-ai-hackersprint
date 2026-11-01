// The question bank: plain questions a person would actually ask, grouped by what they are about. The
// chat offers a few of them at a time and can shuffle, so an empty chat never shows the same four cards.
// They are written for the law the corpus holds (Colorado); each is answerable by citing retrieved cases.

export type QuestionGroup = { id: string; label: string; questions: string[] };

export const QUESTION_GROUPS: QuestionGroup[] = [
  {
    id: "police",
    label: "Police and searches",
    questions: [
      "Can police search my car without a warrant in Colorado?",
      "What does probable cause actually mean?",
      "When can police search my bag or pockets?",
      "Can an officer search my car if they smell marijuana?",
      "Do I have to let police into my home?",
      "Can I be charged with a crime without probable cause?",
      "What if police find evidence of a different crime during an illegal search?",
      "Can evidence from an illegal traffic stop be used against me?",
    ],
  },
  {
    id: "guns",
    label: "Guns",
    questions: [
      "Is it legal to carry a gun without a license in Colorado?",
      "Can I keep a loaded gun in my car in Colorado?",
      "Where is it illegal to carry a firearm in Colorado?",
    ],
  },
  {
    id: "cars",
    label: "Cars",
    questions: [
      "What counts as motor vehicle theft in Colorado?",
      "Can I be charged if I borrow a car and don't give it back?",
      "Is it theft if I take a car for a joyride and return it?",
      "What is the difference between theft and unauthorized use of a vehicle?",
    ],
  },
  {
    id: "home",
    label: "Home and debt",
    questions: [
      "Can creditors take my house in Colorado?",
      "How much of my home is protected from creditors?",
      "What happens to my home if I file for bankruptcy?",
      "Is the money from selling my home protected?",
      "Which debts can a homestead exemption not protect against?",
    ],
  },
  {
    id: "water",
    label: "Water and land",
    questions: [
      "Who gets water first when two ranchers disagree?",
      "Can I use water that runs across my land?",
      "What is a water right, and can it be sold?",
      "What happens if a neighbor uses more than their share of water?",
    ],
  },
  {
    id: "deeper",
    label: "Deeper questions",
    questions: [
      "Does a severed mineral estate keep the Colorado homestead exemption?",
      "Are the proceeds of a homestead sale still exempt in a savings account?",
      "How does a bankruptcy estate treat a recorded homestead exemption?",
      "Which debts does a homestead exemption defeat in Colorado?",
    ],
  },
];

/** A fresh random handful across every group except the deeper ones, so the first cards are easy ones. */
export function popularQuestions(count = 4, random: () => number = Math.random): string[] {
  const easy = QUESTION_GROUPS.filter((group) => group.id !== "deeper");
  // One from each easy group first, so the handful covers different subjects, then fill from the rest.
  const picks = easy.map((group) => group.questions[Math.floor(random() * group.questions.length)]);
  const rest = easy.flatMap((group) => group.questions).filter((question) => !picks.includes(question));
  while (picks.length < count && rest.length) picks.push(rest.splice(Math.floor(random() * rest.length), 1)[0]);
  return shuffle(picks, random).slice(0, count);
}

/** `count` questions from one group, in a random order. */
export function groupQuestions(id: string, count = 4, random: () => number = Math.random): string[] {
  const group = QUESTION_GROUPS.find((item) => item.id === id);
  return group ? shuffle(group.questions, random).slice(0, count) : [];
}

function shuffle<T>(items: T[], random: () => number): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
