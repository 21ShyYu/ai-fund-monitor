import type { NextAuthOptions } from "next-auth";
import GitHubProvider from "next-auth/providers/github";

export const authOptions: NextAuthOptions = {
  providers: [
    GitHubProvider({
      clientId: process.env.GITHUB_ID || "",
      clientSecret: process.env.GITHUB_SECRET || ""
    })
  ],
  session: {
    strategy: "jwt"
  },
  callbacks: {
    async jwt({ token, profile }) {
      if (profile && "login" in profile) {
        token.githubLogin = String(profile.login);
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).githubLogin = token.githubLogin;
      return session;
    }
  }
};

